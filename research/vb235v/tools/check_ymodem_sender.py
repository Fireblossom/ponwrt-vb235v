#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Wire-contract fault tests against pinned U-Boot YMODEM behavior."""
import binascii
from ymodem_sender import ACK, CAN, CRC, EOT, NAK, SOH, STX, Sender, TransferError, FinalAcknowledgementMissing, frame


class Peer:
    def __init__(self, *, first_nak=False, lose_ack=False, two_eot=False,
                 final_drop=False, cancel=False, fragment=0):
        self.rx=bytearray();self.tx=bytearray((CRC,));self.phase='metadata'
        self.now=0.;self.next=1;self.data=bytearray();self.size=0
        self.first_nak=first_nak;self.lose_ack=lose_ack;self.two_eot=two_eot
        self.final_drop=final_drop;self.cancel=cancel;self.fragment=fragment
        self.injections=set();self.sequences=[];self.eots=0

    def clock(self):return self.now
    def read(self):
        self.now+=.1
        data=bytes(self.tx);self.tx.clear();return data
    def write(self,data):
        count=min(len(data),self.fragment) if self.fragment else len(data)
        self.rx.extend(data[:count])
        while self.rx:
            if self.rx[0]==EOT:
                del self.rx[0];self.eots+=1
                assert self.phase=='data' and len(self.data)>=self.size
                if self.two_eot and self.eots==1:self.tx.append(NAK);continue
                self.tx.extend((ACK,ACK,CRC));self.phase='end';continue
            assert self.rx[0] in (SOH,STX)
            length=128 if self.rx[0]==SOH else 1024
            if len(self.rx)<length+5:break
            block=bytes(self.rx[:length+5]);del self.rx[:length+5]
            assert block[1]^block[2]==255
            payload=block[3:-2]
            assert binascii.crc_hqx(payload,0)==int.from_bytes(block[-2:],'big')
            sequence=block[1]
            if self.phase=='metadata':
                assert sequence==0 and length==128
                filename,size,*_=payload.split(b'\0');assert filename==b'cpu-mini.itb'
                self.size=int(size);self.phase='data';self.tx.append(ACK)
            elif self.phase=='data':
                if self.cancel:self.tx.extend((CAN,CAN));continue
                if self.first_nak and 'nak' not in self.injections:
                    self.injections.add('nak');self.tx.append(NAK);continue
                if sequence==((self.next-1)&255):
                    self.tx.append(ACK);continue # Lost ACK; never append twice.
                assert sequence==self.next
                self.sequences.append(sequence);self.data.extend(payload)
                self.next=(self.next+1)&255
                if self.lose_ack and 'ack' not in self.injections:
                    self.injections.add('ack');continue
                self.tx.append(ACK)
            else:
                assert sequence==0 and length==128 and payload==bytes(128)
                self.phase='done'
                if not self.final_drop:self.tx.append(ACK)
        return count


def run(data,**options):
    peer=Peer(**options);progress=[]
    sender=Sender(peer.read,peer.write,clock=peer.clock,timeout=.5,retries=4,
                  progress=lambda at,total,retries:progress.append((at,total,retries)))
    result=sender.send(data,'cpu-mini.itb')
    assert peer.phase=='done' and bytes(peer.data[:peer.size])==data
    assert peer.size==len(data) and result['bytes']==len(data)
    assert progress[-1][:2]==(len(data),len(data))
    return peer,result


assert binascii.crc_hqx(b'123456789',0)==0x31c3
for length in (1,127,128,129,1023,1024,1025,3077):
    run(bytes((i%251 for i in range(length))))
run(b'preserve-real-end-bytes\x1a\x1a\x1a')
peer,result=run(bytes(300*1024));assert 0 in peer.sequences and peer.sequences[-1]==44
peer,result=run(b'payload'*400,first_nak=True);assert result['retries']==1
peer,result=run(b'payload'*400,lose_ack=True);assert result['retries']==1
run(b'payload'*400,two_eot=True)
run(b'payload'*400,fragment=37)
try:run(b'payload',cancel=True)
except TransferError:pass
else:raise AssertionError('receiver cancellation ignored')
try:run(b'payload',final_drop=True)
except FinalAcknowledgementMissing:pass
else:raise AssertionError('missing terminal ACK counted as success')
for name in ('../bad','bad file','bad\x00name','汉字'):
    peer=Peer()
    try:Sender(peer.read,peer.write,clock=peer.clock).send(b'data',name)
    except ValueError:assert not peer.rx
    else:raise AssertionError('unsafe metadata accepted')
peer=Peer();peer.tx=bytearray((NAK,))
try:Sender(peer.read,peer.write,clock=peer.clock).send(b'data','cpu-mini.itb')
except TransferError:pass
else:raise AssertionError('non-CRC handshake accepted')
print('YMODEM CRC, exact length, sequence wrap, NAK, lost ACK, two-EOT, partial writes, cancel and uncertain final ACK: PASS')
