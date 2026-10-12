"""
PHASE 6 - OS-Ken ENFORCEMENT APP (needs OS-Ken + OVS; NOT tested in the sandbox)
Learning switch + a tiny UDP command channel.  The engine sends {"host":"h3","action":"DROP"} to
127.0.0.1:9999 and this app installs / removes a high-priority OpenFlow rule on every switch.

    osken-manager controller/enforcer.py
Mininet must use:  RemoteController('c0', ip='127.0.0.1', port=6653)
"""
import json
import socket
import threading

from os_ken.base import app_manager
from os_ken.controller import ofp_event
from os_ken.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, set_ev_cls
from os_ken.lib.packet import packet, ethernet
from os_ken.ofproto import ofproto_v1_3

PRIORITY = 100


class TrustFlowEnforcer(app_manager.OSKenApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.dps, self.mac_to_port = {}, {}
        threading.Thread(target=self._listen, daemon=True).start()

    # ---- normal L2 learning so the network works at all ----
    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def _features(self, ev):
        dp = ev.msg.datapath; p = dp.ofproto_parser; o = dp.ofproto
        self.dps[dp.id] = dp
        self._flow(dp, 0, p.OFPMatch(), [p.OFPActionOutput(o.OFPP_CONTROLLER, o.OFPCML_NO_BUFFER)])

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in(self, ev):
        msg = ev.msg; dp = msg.datapath; o = dp.ofproto; p = dp.ofproto_parser
        eth = packet.Packet(msg.data).get_protocols(ethernet.ethernet)[0]
        table = self.mac_to_port.setdefault(dp.id, {})
        table[eth.src] = msg.match["in_port"]
        out = table.get(eth.dst, o.OFPP_FLOOD)
        acts = [p.OFPActionOutput(out)]
        if out != o.OFPP_FLOOD:
            self._flow(dp, 1, p.OFPMatch(in_port=msg.match["in_port"], eth_dst=eth.dst, eth_src=eth.src), acts)
        dp.send_msg(p.OFPPacketOut(datapath=dp, buffer_id=msg.buffer_id, in_port=msg.match["in_port"],
                                   actions=acts, data=msg.data if msg.buffer_id == o.OFP_NO_BUFFER else None))

    def _flow(self, dp, prio, match, actions, delete=False):
        o, p = dp.ofproto, dp.ofproto_parser
        inst = [p.OFPInstructionActions(o.OFPIT_APPLY_ACTIONS, actions)] if actions else []
        if delete:
            dp.send_msg(p.OFPFlowMod(datapath=dp, command=o.OFPFC_DELETE_STRICT, priority=prio,
                                     match=match, out_port=o.OFPP_ANY, out_group=o.OFPG_ANY))
        else:
            dp.send_msg(p.OFPFlowMod(datapath=dp, priority=prio, match=match, instructions=inst))

    # ---- TrustFlow command channel ----
    def _listen(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.bind(("127.0.0.1", 9999))
        while True:
            cmd = json.loads(s.recvfrom(2048)[0])
            self.apply(cmd["host"], cmd["action"])

    def apply(self, host, action):
        ip = f"10.0.0.{host[1:]}"
        for dp in self.dps.values():
            p = dp.ofproto_parser
            match = p.OFPMatch(eth_type=0x0800, ipv4_src=ip)
            if action in ("ALLOW", "ALLOW+LOG"):
                self._flow(dp, PRIORITY, match, [], delete=True)
            elif action in ("DROP", "QUARANTINE"):
                self._flow(dp, PRIORITY, match, [])          # empty action list = drop
            elif action == "RATE_LIMIT":
                o = dp.ofproto
                dp.send_msg(p.OFPMeterMod(dp, o.OFPMC_ADD, o.OFPMF_PKTPS, int(host[1:]) + 100,
                                          [p.OFPMeterBandDrop(rate=50, burst_size=10)]))
                dp.send_msg(p.OFPFlowMod(datapath=dp, priority=PRIORITY, match=match, instructions=[
                    p.OFPInstructionMeter(int(host[1:]) + 100),
                    p.OFPInstructionActions(o.OFPIT_APPLY_ACTIONS, [p.OFPActionOutput(o.OFPP_NORMAL)])]))
        self.logger.info("enforced %s -> %s", host, action)
