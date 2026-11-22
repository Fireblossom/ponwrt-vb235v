#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
# Last defaults phase: migrate only this board's untouched isolated LAN.
# --check reports the plan without writing configuration or restarting services.
set -eu
action=${1:---check}
case "$action" in --check|--apply) ;; *) exit 2 ;; esac
root=${PONWRT_M83_TEST_ROOT:-}
if [ -n "$root" ]; then
    case "$root" in /tmp/m83-management-test-*) ;; *) exit 2 ;; esac
    uci_bin=${PONWRT_M83_TEST_UCI:?}
else
    [ "$(cat /tmp/sysinfo/board_name 2>/dev/null)" = tplink,vb235v ] || exit 0
    [ "$(id -u)" = 0 ] || exit 1
    uci_bin=/sbin/uci
fi
config="$root/etc/config"
tmp="$root/tmp"
mkdir -p "$tmp"
umask 077
lock="$tmp/ponwrt-m83-management.lock"
if ! mkdir "$lock" 2>/dev/null; then
    printf '%s\n' '{"state":"busy","code":"MANAGEMENT_LOCKED"}'
    exit 1
fi
work=$(mktemp -d "$tmp/ponwrt-m83-management.XXXXXX")
cleanup() {
    case "$work" in "$tmp"/ponwrt-m83-management.*) rm -rf "$work" ;; esac
    rmdir "$lock"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM HUP
mkdir "$work/config" "$work/original" "$work/delta"
report() {
    result=$(printf '{"state":"%s","code":"%s","eth1_bridged":false}\n' "$1" "$2")
    printf '%s\n' "$result"
    if [ "$action" = --apply ]; then
        mkdir -p "$root/etc/ponwrt"
        printf '%s\n' "$result" > "$root/etc/ponwrt/management-m83.json.new"
        chmod 600 "$root/etc/ponwrt/management-m83.json.new"
        sync
        mv "$root/etc/ponwrt/management-m83.json.new" "$root/etc/ponwrt/management-m83.json"
        sync
    fi
}
skip() { report skipped_custom "$1"; exit 0; }
for name in network dhcp firewall uhttpd dropbear; do
    [ -f "$config/$name" ] && [ ! -L "$config/$name" ] || skip MISSING_REGULAR_CONFIG
    [ ! -e "$tmp/.uci/$name" ] || skip UNCOMMITTED_UCI_CHANGES
    cp "$config/$name" "$work/config/$name"
    cp "$config/$name" "$work/original/$name"
done
uc() { "$uci_bin" -q -c "$work/config" -t "$work/delta" "$@"; }
get() { uc get "$1" 2>/dev/null || :; }
[ "$(get network.lan)" = interface ] || skip CUSTOM_LAN
[ "$(get network.lan.proto)" = static ] || skip CUSTOM_LAN
[ "$(get network.lan.ipaddr)" = 192.168.235.1 ] || skip CUSTOM_LAN_ADDRESS
[ "$(get network.lan.netmask)" = 255.255.255.0 ] || skip CUSTOM_LAN_ADDRESS
keys=$(uc show network.lan | sed -n 's/^network\.lan\.\([^=]*\)=.*/\1/p' | LC_ALL=C sort)
[ "$keys" = "$(printf '%s\n' device ipaddr netmask proto)" ] || skip CUSTOM_LAN_OPTIONS
[ "$(get network.lan)" = interface ] || skip CUSTOM_LAN_SECTION
state=$(get network.lan.device)
case "$state" in lan-test|br-lan) ;; *) skip CUSTOM_LAN_DEVICE ;; esac
[ "$(get dhcp.lan.interface)" = lan ] && [ "$(get dhcp.lan.start)" = 2 ] &&
 [ "$(get dhcp.lan.limit)" = 1 ] && [ "$(get dhcp.lan.leasetime)" = 1h ] || skip CUSTOM_DHCP
case "$(get dhcp.lan.dhcp_option)" in '3 6'|'6 3') ;; *) skip DHCP_ADVERTISES_GATEWAY_OR_DNS ;; esac
[ "$(get firewall.@zone[0].name)" = lan ] && [ "$(get firewall.@zone[0].input)" = ACCEPT ] || skip CUSTOM_LAN_FIREWALL
case " $(get firewall.@zone[0].network) " in *' lan '*) ;; *) skip CUSTOM_LAN_FIREWALL ;; esac
[ "$(get uhttpd.main.home)" = /www ] && [ "$(get uhttpd.main.ubus_prefix)" = /ubus ] || skip CUSTOM_WEB_ROOT
[ "$(get uhttpd.main.cert)" = /etc/uhttpd.crt ] && [ "$(get uhttpd.main.key)" = /etc/uhttpd.key ] || skip CUSTOM_TLS_IDENTITY
case "$(get uhttpd.main.no_ubusauth)" in ''|0) ;; *) skip UNSAFE_UBUS_AUTH ;; esac
case "$(get uhttpd.main.ubus_cors)" in ''|0) ;; *) skip CUSTOM_CORS ;; esac
http=$(get uhttpd.main.listen_http);https=$(get uhttpd.main.listen_https)
case " $http " in *' 192.168.235.1:80 '*) ;; *) skip CUSTOM_HTTP_LISTENER ;; esac
for address in $http; do
    case "$address" in 192.168.235.1:80|169.254.211.1:80|169.254.235.1:80) ;; *) skip CUSTOM_HTTP_LISTENER ;; esac
done
for address in $https; do
    case "$address" in 192.168.235.1:443|169.254.211.1:443|169.254.235.1:443) ;; *) skip CUSTOM_HTTPS_LISTENER ;; esac
done
if [ "$state" = lan-test ]; then
    case "$(uc show network)" in *eth2*|*br-lan*|*ponwrt_recovery*) skip PORT_OR_BRIDGE_ALREADY_ASSIGNED ;; esac
    uc set network.ponwrt_lan_bridge=device
    uc set network.ponwrt_lan_bridge.name=br-lan
    uc set network.ponwrt_lan_bridge.type=bridge
    uc add_list network.ponwrt_lan_bridge.ports=lan-test
    uc add_list network.ponwrt_lan_bridge.ports=eth2
    uc set network.ponwrt_lan_bridge.stp=1
    uc set network.ponwrt_lan_bridge.forward_delay=2
    uc set network.lan.device=br-lan
    uc set network.ponwrt_recovery=interface
    uc set network.ponwrt_recovery.device=br-lan
    uc set network.ponwrt_recovery.proto=static
    uc set network.ponwrt_recovery.ipaddr=169.254.235.1
    uc set network.ponwrt_recovery.netmask=255.255.0.0
else
    [ "$(get network.ponwrt_lan_bridge.name)" = br-lan ] &&
     [ "$(get network.ponwrt_lan_bridge.type)" = bridge ] &&
     [ "$(get network.ponwrt_lan_bridge.stp)" = 1 ] &&
     [ "$(get network.ponwrt_lan_bridge.forward_delay)" = 2 ] || skip CUSTOM_BRIDGE
    case "$(get network.ponwrt_lan_bridge.ports)" in 'lan-test eth2'|'eth2 lan-test') ;; *) skip CUSTOM_BRIDGE_PORTS ;; esac
    keys=$(uc show network.ponwrt_lan_bridge | sed -n 's/^network\.ponwrt_lan_bridge\.\([^=]*\)=.*/\1/p' | LC_ALL=C sort)
    [ "$keys" = "$(printf '%s\n' forward_delay name ports stp type)" ] || skip CUSTOM_BRIDGE_OPTIONS
    [ "$(get network.ponwrt_recovery.proto)" = static ] &&
     [ "$(get network.ponwrt_recovery.device)" = br-lan ] &&
     [ "$(get network.ponwrt_recovery.ipaddr)" = 169.254.235.1 ] &&
     [ "$(get network.ponwrt_recovery.netmask)" = 255.255.0.0 ] || skip CUSTOM_FALLBACK
    keys=$(uc show network.ponwrt_recovery | sed -n 's/^network\.ponwrt_recovery\.\([^=]*\)=.*/\1/p' | LC_ALL=C sort)
    [ "$keys" = "$(printf '%s\n' device ipaddr netmask proto)" ] || skip CUSTOM_FALLBACK_OPTIONS
    case "$(uc show network | sed '/^network\.ponwrt_lan_bridge\./d')" in *eth2*) skip PORT_ALREADY_ASSIGNED_ELSEWHERE ;; esac
fi
if [ "$state" = br-lan ] &&
 [ "$http" = '192.168.235.1:80 169.254.235.1:80' ] &&
 [ "$https" = '192.168.235.1:443 169.254.235.1:443' ] &&
 [ "$(get uhttpd.main.redirect_https)" = 1 ] &&
 [ "$(get uhttpd.main.no_dirlists)" = 1 ] && [ "$(get uhttpd.main.no_symlinks)" = 1 ]; then
    report configured ALREADY_CONFIGURED
    exit 0
fi
uc delete uhttpd.main.listen_http
uc add_list uhttpd.main.listen_http=192.168.235.1:80
uc add_list uhttpd.main.listen_http=169.254.235.1:80
uc delete uhttpd.main.listen_https 2>/dev/null || :
uc add_list uhttpd.main.listen_https=192.168.235.1:443
uc add_list uhttpd.main.listen_https=169.254.235.1:443
uc set uhttpd.main.redirect_https=1
uc set uhttpd.main.no_dirlists=1
uc set uhttpd.main.no_symlinks=1
uc commit uhttpd
uc commit network
if [ "$action" = --check ]; then report ready KNOWN_DEFAULT_MIGRATION_READY; exit 0; fi
# Configuration transaction: retain the primary address throughout. Commit
# listeners first; a power loss between files still leaves primary LAN usable.
for name in uhttpd network; do
    cmp -s "$config/$name" "$work/original/$name" || { report rejected CONFIG_CHANGED_DURING_PLAN; exit 1; }
done
for name in uhttpd network; do
    cp "$work/config/$name" "$config/$name.m83-new"
    chmod 600 "$config/$name.m83-new"
    sync
    mv "$config/$name.m83-new" "$config/$name"
    sync
done
report configured KNOWN_DEFAULT_MIGRATION_APPLIED
