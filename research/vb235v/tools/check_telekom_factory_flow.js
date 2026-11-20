#!/usr/bin/env node
// SPDX-License-Identifier: GPL-2.0-only
// Replay only the pinned original function with modeled callbacks; no browser/network.
'use strict';
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const zlib = require('zlib');
const vm = require('vm');
const assert = require('assert');

if (process.argv.length !== 4) {
  throw new Error('usage: check_telekom_factory_flow.js EXTRACTED_FACTORY_ROOT REPORT');
}
const root = process.argv[2];
const output = process.argv[3];
const uiBytes = fs.readFileSync(path.join(root, 'web/main/qsIsp.htm'));
const profileBytes = fs.readFileSync(path.join(root, 'web/js/ispprofileV3.json.gz'));
const sha = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
assert.strictEqual(sha(uiBytes), 'e24a82123335e5989b3250b277cc767b50ab2f3b8aa315a0eb946ad436b178dd');
assert.strictEqual(sha(profileBytes), 'a1a6db3f7e4810547dee6d68e63931875685bdf633f76b92e40d3d729d6e6ac0');
const profile = JSON.parse(zlib.gunzipSync(profileBytes)).region_isp.DE.Telekom.Auto_DSL.config;
const source = uiBytes.toString('utf8');
const start = source.indexOf('    function qsTelekomAutoDetect() {');
const end = source.indexOf('\n    function getGatewayInfo()', start);
assert(start >= 0 && end > start && end - start < 16000);
const code = source.slice(start, end);
assert(code.trim().endsWith('}'));
const candidates = profile.internet.map(candidate => candidate.access_mode === 'ADSL'
  ? [candidate.name, candidate.vpi, candidate.vci, candidate.conn_type, candidate.atm_encap, candidate.vtag]
  : [candidate.name, candidate.vid, candidate.conn_type]);
const expected = [
  {name: 'Telekom_ADSL', serviceType: 'Internet', accessMode: 'ADSL', vpi: 1, vci: 32,
    connType: 'PPPoE', ATMEncapsulation: 'LLC', vtag: 7},
  {name: 'Telekom_VDSL', serviceType: 'Internet', accessMode: 'VDSL', vid: 7, connType: 'PPPoE'}
];

function replay(existingProfiles, rejectAdd, reverseCallbacks) {
  const events = [];
  const queue = [];
  let requested = false;
  let loginMatches = false;
  const added = [];
  const initial = Array.from({length: existingProfiles}, (_, index) => ({stack: [index + 1, 0, 0, 0]}));
  const $ = {
    model: 'VB235v-fixture',
    qd: {dsl: {internetArray: candidates, isp: 'Telekom', ispName: 'Telekom'}, internetDiag: 0},
    qf: {load: page => events.push({operation: 'next-page', page})},
    createLock: (count, callback) => {
      let remaining = Math.max(1, count);
      let fired = false;
      return () => {
        remaining -= 1;
        if (remaining <= 0 && !fired) { fired = true; callback(); }
      };
    },
    dm: {
      getListSync: request => {
        assert.strictEqual(request.oid, 'DEV2_X_TP_AUTODETECT_PROF');
        events.push({operation: 'list-profiles'});
        request.callback.success(initial);
      },
      del: request => {
        assert.strictEqual(request.oid, 'DEV2_X_TP_AUTODETECT_PROF');
        events.push({operation: 'delete-profile'});
        queue.push(() => request.callback.success({}));
      },
      add: request => {
        assert.strictEqual(request.oid, 'DEV2_X_TP_AUTODETECT_PROF');
        const data = JSON.parse(JSON.stringify(request.data));
        added.push(data);
        events.push({operation: 'add-profile', name: data.name});
        queue.push(() => {
          const failed = data.name === rejectAdd;
          events.push({operation: 'add-result', name: data.name, success: !failed});
          request.callback[failed ? 'fail' : 'success']({});
        });
      },
      set: request => {
        assert.strictEqual(request.oid, 'DEV2_X_TP_AUTODETECT');
        assert.strictEqual(request.data.autoDetectState, 'Requested');
        loginMatches = request.data.PPPUsername === profile.preset_pppoe_username &&
          request.data.PPPPassword === profile.preset_pppoe_password;
        assert(loginMatches);
        requested = true;
        // Deliberately omit all login values from the replay report.
        events.push({operation: 'request-autodetect', preset_matches_database: loginMatches});
        queue.push(() => request.callback.success({}));
      }
    }
  };
  const context = vm.createContext({$, flowSteps: [{}], currIndex: 0},
    {codeGeneration: {strings: false, wasm: false}});
  new vm.Script(code + '\nqsTelekomAutoDetect();').runInContext(context, {timeout: 500});
  let callbacks = 0;
  while (queue.length) {
    assert(++callbacks <= 32);
    (reverseCallbacks ? queue.pop() : queue.shift())();
  }
  assert.strictEqual(added.length, 2);
  assert.deepStrictEqual(added, expected);
  assert(requested && loginMatches);
  const requestedAt = events.findIndex(event => event.operation === 'request-autodetect');
  const completedBeforeRequest = events.slice(0, requestedAt).filter(event => event.operation === 'add-result');
  assert.strictEqual(completedBeforeRequest.length, 2);
  assert.strictEqual(events.filter(event => event.operation === 'delete-profile').length, existingProfiles);
  return {
    initial_profiles: existingProfiles, callbacks_completed_in_reverse_order: reverseCallbacks,
    rejected_profile: rejectAdd || null, all_profile_callbacks_precede_request: true,
    factory_login_matches_database: loginMatches, autodetect_requested: requested,
    original_requests_autodetect_after_a_profile_error: Boolean(rejectAdd),
    events
  };
}

const cases = [replay(0, null, false), replay(2, null, false), replay(2, null, true),
  replay(0, 'Telekom_ADSL', false), replay(2, 'Telekom_VDSL', true)];
const report = {
  classification: 'original pinned quick-setup function with modeled lock/backend callbacks',
  quick_setup_sha256: sha(uiBytes), provider_database_sha256: sha(profileBytes),
  executed_function: 'qsTelekomAutoDetect', cases_passed: cases.length,
  generated_profiles: expected, cases,
  callback_backend_modeled: true, actual_network_requests: 0, customer_saved_credentials_read: false,
  DSL_sync_verified: false, PPPoE_login_verified: false, ACS_provisioning_verified: false
};
fs.writeFileSync(output, JSON.stringify(report, null, 2) + '\n');
console.log(JSON.stringify({cases_passed: cases.length, original_profile_parameters_match: true,
  factory_login_matches_database: true, partial_failure_behavior_recorded: true,
  actual_network_requests: 0}, null, 2));
