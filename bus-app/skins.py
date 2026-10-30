# -*- coding: utf-8 -*-
"""两套视觉皮肤。

A = 素纸：纯白纸面、细线分隔、只在首页浮一张卡。极简，像打印的时刻表。
B = 站牌：米灰纸背景、首页一块深蓝实心电子站牌、其余页面白面板浮起。

两套都遵守同一条底线：正文对比度 >= 4.5:1，关键数字 >= 7:1，
不做渐变字、不做半透明正文、不靠颜色单独传递信息。
"""

CSS_A = r"""
*{box-sizing:border-box;margin:0;padding:0;-webkit-tap-highlight-color:transparent}
html,body{height:100%}
html{background:#EFEFE9}
body{
  font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",system-ui,sans-serif;
  background:#FAFAF7;color:#1A1C1E;display:flex;flex-direction:column;overflow:hidden;
  -webkit-font-smoothing:antialiased;
  max-width:420px;margin:0 auto;
}

.nav{flex-shrink:0;display:flex;align-items:baseline;gap:10px;padding:19px 20px 13px;background:#FAFAF7}
.back{
  font-size:16px;color:#5A6066;background:none;border:none;
  font-family:inherit;padding:2px 10px 2px 0;cursor:pointer;font-weight:600;
}
.nav .t{font-size:23px;font-weight:700;letter-spacing:-.4px}
.nav .r{
  margin-left:auto;display:inline-flex;align-items:center;gap:6px;
  font-size:15px;color:#8A8F94;font-weight:500;font-variant-numeric:tabular-nums;
}
.live{
  width:6px;height:6px;border-radius:50%;background:#1F9E5A;
  box-shadow:0 0 0 3px rgba(31,158,90,.14);flex-shrink:0;
}

.scroll{flex:1;overflow-y:auto;overflow-x:hidden;padding:0 20px 18px;min-height:0;scrollbar-width:none}
.scroll::-webkit-scrollbar{width:0;height:0;display:none}
.scroll.flush{padding:0 20px}
.scroll.home{display:flex;flex-direction:column;padding:0 16px 12px}

.card{
  background:#fff;border-radius:26px;padding:24px 22px 17px;
  border:1px solid #EAE9E2;
  box-shadow:0 1px 3px rgba(22,32,43,.04);
  cursor:pointer;position:relative;overflow:hidden;
}
.scroll.home .card{flex:1;min-height:0;display:flex;flex-direction:column}
.card.up,.card.dn{background:#fff}
.card.urgent{border-color:#F1CC9E}
.card.urgent::before{
  content:"";position:absolute;left:0;top:0;bottom:0;width:3px;background:#DA6B1C;
}

.ctop{display:flex;align-items:center;gap:9px}
.lineno{font-size:27px;font-weight:700;letter-spacing:-.4px;color:#0E3A63}
.lineno.up,.lineno.dn{color:#0E3A63}
.toward{
  font-size:14px;color:#5C6166;flex:1;min-width:0;
  white-space:normal;overflow-wrap:break-word;line-height:1.3;
}
.swapbtn{
  margin-left:auto;flex-shrink:0;display:inline-flex;align-items:center;gap:5px;
  border:1px solid #DFE3E8;background:#fff;color:#3A4048;
  border-radius:999px;padding:8px 13px;
  font-size:13.5px;font-weight:600;font-family:inherit;
  cursor:pointer;line-height:1;white-space:nowrap;
}
.swapbtn .si{font-size:14px;color:#8A9199}
.swapbtn b{font-size:16px;font-weight:700;color:#0E3A63}
.card.up .swapbtn,.card.dn .swapbtn{color:#3A4048}

.cmid{margin-top:2px}
.main{display:flex;align-items:baseline;gap:6px;margin-top:10px}
.min{
  font-size:96px;font-weight:800;line-height:.84;letter-spacing:-5px;
  color:#0E3A63;font-variant-numeric:tabular-nums;
}
.min.up,.min.dn{color:#0E3A63}
.unit{font-size:22px;font-weight:600;color:#0E3A63}
.unit.up,.unit.dn{color:#0E3A63}
.stxt{font-size:48px;font-weight:800;line-height:1.05;letter-spacing:-1.5px;margin-top:12px;color:#0E3A63}
.stxt.up,.stxt.dn{color:#0E3A63}
.sub{font-size:18px;color:#55595E;margin-top:10px}
.go{color:#C2410C;font-weight:700}

.swin{
  margin-top:16px;padding-top:6px;border-top:1px solid #F0EFE8;
  flex:1;min-height:0;display:flex;flex-direction:column;position:relative;
}
/* 站点列表在固定高度里滚动，初始滚到「我」那一站。
   以前这里是 flex:1 把每行撑开，矮屏幕上整块会被压扁、内容溢出，
   压在卡片底部「看全部」那一行上 —— 连点击都被挡住。 */
.swscroll{
  flex:1;min-height:0;overflow-y:auto;overflow-x:hidden;
  -webkit-overflow-scrolling:touch;scrollbar-width:none;padding-bottom:6px;
}
.swscroll::-webkit-scrollbar{width:0;height:0;display:none}
/* 底部渐隐：最后一行被裁一半看起来像 bug，加层白雾就变成"下面还有"的暗示 */
.swin::after{
  content:"";position:absolute;left:0;right:0;bottom:0;height:16px;
  background:linear-gradient(to top,#fff 12%,rgba(255,255,255,0));
  pointer-events:none;
}
.swabove{font-size:13.5px;color:#9A6A2E;padding:4px 0 2px;flex-shrink:0}
.swrow{position:relative;display:flex;align-items:center;gap:10px;height:46px;flex-shrink:0;padding-left:25px}
.swrow::before{
  content:"";position:absolute;left:4px;top:0;bottom:0;
  width:1.5px;background:#DBDAD1;
}
.swrow:first-child::before{top:50%}
.swrow:last-child::before{bottom:50%}
.swrow .d{
  position:absolute;left:0;top:50%;transform:translateY(-50%);
  width:9px;height:9px;border-radius:50%;background:#fff;
  border:1.5px solid #CFCEC5;box-sizing:border-box;
}
.swrow.mine .d{border:none;background:#0E3A63;box-shadow:0 0 0 4px rgba(14,58,99,.10)}
.swrow.bus .d{border:none;background:#DA6B1C;box-shadow:0 0 0 4px rgba(218,107,28,.13)}
.swrow .n{
  font-size:17px;color:#3C4046;flex:0 1 auto;letter-spacing:-.1px;max-width:68%;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
}
.swrow::after{content:"";flex:1 1 0;height:0}
.swrow.mine .n{font-weight:700;color:#0E3A63}
.swrow .tb{
  font-size:11.5px;font-weight:700;color:#B4550E;background:#FDF0E3;
  border-radius:5px;padding:2px 6px;
}
.swrow .tm2{
  font-size:11.5px;font-weight:700;color:#0E3A63;background:#EAF1F8;
  border-radius:5px;padding:2px 6px;
}

/* ---- 选方向页：两个方向做成两张大卡，别让他去分辨上行下行 ---- */
.dhint{font-size:14.5px;color:#6B7076;padding:2px 4px 14px;line-height:1.5}
.dircard{
  background:#fff;border:1px solid #E9E8E1;border-radius:20px;
  padding:20px 42px 20px 22px;margin-bottom:13px;cursor:pointer;position:relative;
  box-shadow:0 1px 2px rgba(22,32,43,.04);
}
.dircard:active{background:#F6F6F0}
.dircard::after{
  content:"›";position:absolute;right:20px;top:50%;transform:translateY(-50%);
  font-size:22px;color:#D0D0C6;
}
.dtoward{font-size:14px;color:#8A8F94;font-weight:500;letter-spacing:.5px;flex-shrink:0}
.dto{
  display:flex;align-items:baseline;gap:7px;
  font-size:29px;font-weight:800;color:#0E3A63;letter-spacing:-.7px;
  margin-top:4px;line-height:1.22;
}
.dmeta{font-size:14px;color:#7A7F74;margin-top:9px;letter-spacing:.2px}
.dlive{margin-top:9px;display:flex;align-items:baseline;gap:9px}
.dmin{font-size:23px;font-weight:800;color:#C25E00;letter-spacing:-.5px}
.dst2{font-size:14.5px;color:#6B7076}
.dnum{font-size:15px;color:#6B7076}

/* 搜索结果里方向后面的站数，比站名淡一档，不抢「往哪」 */
.dstop{font-size:13px;color:#8A8F94;font-weight:400}

/* 导航栏右侧的文字按钮（站牌页「换站」） */
.navlink{
  margin-left:auto;font-size:15px;font-weight:600;color:#0E3A63;
  background:none;border:none;font-family:inherit;cursor:pointer;
  padding:10px 0 10px 12px;
}

.cfoot{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-top:4px;padding-top:13px;border-top:1px solid #F0EFE8;flex-shrink:0;position:relative;z-index:2}
.swall{
  font-size:15px;color:#0E3A63;font-weight:600;white-space:nowrap;
  background:none;border:none;font-family:inherit;cursor:pointer;
  padding:8px 2px 8px 0;margin:-8px 0;   /* 撑大点击热区，但不改变视觉高度 */
  display:inline-flex;align-items:center;gap:3px;
}
.swall:active{opacity:.6}

/* 到站提醒 */
.remlink{
  display:inline-flex;align-items:center;gap:4px;flex-shrink:0;
  font-size:13.5px;font-weight:500;color:#9AA096;
  background:none;border:none;padding:5px 0;
  font-family:inherit;cursor:pointer;line-height:1.2;white-space:nowrap;
}
.remlink.on{color:#B45309;font-weight:600}
.remlink .ri{font-size:12px;opacity:.85}

.banner{
  position:fixed;top:0;left:0;right:0;max-width:420px;margin:0 auto;z-index:50;
  background:#FFF9F2;border-bottom:1.5px solid #F0D6B4;
  box-shadow:0 14px 34px -16px rgba(24,32,42,.45);
  padding:15px 16px;display:flex;align-items:center;gap:13px;
  transform:translateY(-115%);transition:transform .32s cubic-bezier(.2,.85,.3,1);
}
.banner.show{transform:translateY(0)}
.banner .btext{flex:1;min-width:0}
.banner .bt{font-size:22px;font-weight:800;color:#A8480B;line-height:1.15;letter-spacing:-.3px}
.banner .bs{font-size:15px;color:#3C4046;margin-top:3px}
.banner.hot{background:#FFF3E6;border-bottom-color:#F2BE85}
.banner .bx{
  flex-shrink:0;background:#A8480B;color:#fff;border:none;border-radius:11px;
  padding:13px 15px;font-size:15px;font-weight:700;font-family:inherit;cursor:pointer;
}
.banner .bx:active{transform:scale(.97)}

.mask{
  position:fixed;inset:0;background:rgba(16,24,32,.40);z-index:60;
  opacity:0;pointer-events:none;transition:opacity .2s;
}
.mask.show{opacity:1;pointer-events:auto}

.sheet{
  position:fixed;left:0;right:0;bottom:0;max-width:420px;margin:0 auto;z-index:61;
  background:#fff;border-radius:24px 24px 0 0;padding:22px 18px 34px;
  transform:translateY(112%);transition:transform .3s cubic-bezier(.2,.85,.3,1);
  box-shadow:0 -12px 40px -20px rgba(24,32,42,.5);
}
.sheet.show{transform:translateY(0)}
.sheet h4{font-size:19px;font-weight:700;letter-spacing:-.2px}
.sheet .hint{font-size:16.5px;color:#1A1C1E;font-weight:600;line-height:1.5;margin-top:8px}
.opts{display:flex;gap:9px;margin:16px 0 12px}
.opt{
  flex:1;height:60px;border:1.5px solid #E2E1D9;border-radius:15px;background:#fff;
  font-size:16px;font-weight:600;font-family:inherit;color:#2A2E33;cursor:pointer;
  display:flex;flex-direction:column;align-items:center;justify-content:center;gap:1px;
}
.opt small{font-size:12.5px;font-weight:500;color:#6B7076}
.opt.sel{background:#0E3A63;border-color:#0E3A63;color:#fff}
.opt.sel small{color:rgba(255,255,255,.72)}
.sheet .limit{
  font-size:13.5px;color:#8A4B10;line-height:1.5;margin-top:12px;
  background:#FFF7EC;border-left:3px solid #E8A24A;border-radius:6px;
  padding:9px 11px;
}

.sheet .off{
  width:100%;height:54px;border:none;border-radius:14px;background:#F2F1EA;color:#5A5F55;
  font-size:16px;font-weight:600;font-family:inherit;cursor:pointer;
}

.sec{font-size:13px;color:#96998F;margin:16px 2px 6px;font-weight:500;letter-spacing:.2px}

.row{
  display:flex;align-items:center;gap:12px;
  padding:19px 2px;border-bottom:1px solid #EAE9E2;cursor:pointer;
}
.row:active{background:#F3F3ED}
.row .ln{
  font-size:22px;font-weight:700;color:#1A1C1E;min-width:84px;letter-spacing:-.4px;
  font-variant-numeric:tabular-nums;
}
.row .dst{flex:1;font-size:15.5px;color:#6B7076;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.row .tm{
  font-size:25px;font-weight:700;color:#0E3A63;text-align:right;
  white-space:nowrap;font-variant-numeric:tabular-nums;letter-spacing:-.8px;
  min-width:68px;
}
.row .tm.hot{color:#C2410C;font-size:19px;letter-spacing:0}
.row .tm.wait{font-size:16px;font-weight:500;color:#9A9E96;letter-spacing:0}
.row .arrow{color:#CFCFC6;font-size:17px}
.row.first{border-top:none}
.srow .ln{min-width:auto;margin-right:2px}

.more{padding:22px 4px;font-size:16px;color:#0E3A63;cursor:pointer;font-weight:600}

.sbar{display:flex;gap:10px;padding:2px 16px 16px;flex-shrink:0}
.sinput{
  flex:1;height:56px;border:1px solid #DFDED6;border-radius:16px;
  padding:0 16px;font-size:20px;font-family:inherit;outline:none;
  background:#fff;color:#111;
}
.sinput:focus{border-color:#0E3A63;box-shadow:0 0 0 3px rgba(14,58,99,.08)}
.sbtn{
  width:80px;height:56px;border:none;border-radius:16px;background:#16202B;color:#fff;
  font-size:18px;font-weight:600;font-family:inherit;cursor:pointer;
}

.lhead{padding:2px 20px 14px;flex-shrink:0}
.lh1{display:flex;align-items:center;gap:12px}
.lh2{font-size:22px;font-weight:600;color:#1A1C1E;letter-spacing:-.2px}
.lh2 b{font-weight:700}
.swap{
  margin-left:auto;flex-shrink:0;display:inline-flex;align-items:center;gap:5px;
  border:1px solid #DFE3E8;background:#fff;color:#0E3A63;
  border-radius:999px;padding:10px 16px;
  font-size:14px;font-weight:600;font-family:inherit;cursor:pointer;line-height:1;
}
.lh3{font-size:13px;color:#96998F;margin-top:7px}
.noreal{
  background:#FDF6E7;color:#8A5A16;border-radius:10px;
  padding:10px 13px;font-size:13.5px;margin-top:11px;line-height:1.5;
}

.tl{position:relative;padding:8px 0 36px}
.stop{display:flex;align-items:center;gap:14px;padding:0 20px;height:60px;position:relative}
.stop::after{content:"";flex:1 1 0;height:0}
.stop .rail{position:absolute;left:36.25px;top:0;bottom:0;width:1.5px;background:#DBDAD0}
.stop:first-child .rail{top:50%}
.stop:last-child .rail{bottom:50%}
.dot{
  position:relative;z-index:1;width:12px;height:12px;border-radius:50%;
  background:#FAFAF7;border:1.5px solid #CFCEC5;flex:0 0 12px;margin-left:11px;
  box-sizing:border-box;
}
.dot.mine{border:none;background:#0E3A63;box-shadow:0 0 0 4px rgba(14,58,99,.16)}
.dot.bus{border:none;background:#DA6B1C;box-shadow:0 0 0 4px rgba(218,107,28,.17)}
.sname{
  font-size:20px;color:#2E3238;flex:0 1 auto;letter-spacing:-.2px;
  max-width:66%;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
}
.sname.mine{font-weight:700;color:#0E3A63}
.tagme{font-size:12px;font-weight:700;color:#0E3A63;background:#EAF1F8;border-radius:5px;padding:3px 7px}
.tagbus{font-size:12px;font-weight:700;color:#B4550E;background:#FDF0E3;border-radius:5px;padding:3px 7px}
.stop.mine,.stop.busrow{background:transparent}
.busmeta{font-size:13px;color:#B0600E;margin-left:8px}

.btnrow{display:flex;gap:10px;padding:10px 16px 18px;flex-shrink:0}
.btn{
  flex:1;height:62px;border:none;border-radius:18px;font-size:18px;
  font-weight:600;font-family:inherit;cursor:pointer;
}
.btn.p{background:#16202B;color:#fff}
.btn.s{background:#EFEEE7;color:#2A2E33}
.btn.on{background:#0E3A63;color:#fff}
.tip{font-size:12.5px;color:#A0A49A;text-align:center;padding:10px 0 4px}
.loading{padding:64px 20px;text-align:center;font-size:18px;color:#8A8F84}
.err{background:#FDF0EE;border:1px solid #F0C4BC;border-radius:16px;padding:20px;margin:16px 4px}
.err h3{font-size:20px;color:#A33224;margin-bottom:8px}
.err p{font-size:15.5px;color:#55595E;line-height:1.55}
"""


CSS_B = r"""
*{box-sizing:border-box;margin:0;padding:0;-webkit-tap-highlight-color:transparent}
html,body{height:100%}
html{background:#D4D5CC}
body{
  font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",system-ui,sans-serif;
  background:#E8E9E1;color:#12171C;display:flex;flex-direction:column;overflow:hidden;
  -webkit-font-smoothing:antialiased;
  max-width:420px;margin:0 auto;
}

/* ---------------------------------------------------------- 顶栏 */
.nav{flex-shrink:0;display:flex;align-items:center;gap:10px;padding:20px 20px 13px}
.nav .t{font-size:22px;font-weight:700;letter-spacing:-.4px;color:#0F2537}
.nav .r{
  margin-left:auto;display:inline-flex;align-items:center;gap:6px;
  font-size:14px;color:#75786F;font-weight:500;font-variant-numeric:tabular-nums;
}
.live{
  width:6px;height:6px;border-radius:50%;background:#1F9E5A;
  box-shadow:0 0 0 3px rgba(31,158,90,.15);flex-shrink:0;
}
.back{
  font-size:16px;color:#37475A;background:none;border:none;
  font-family:inherit;padding:2px 10px 2px 0;cursor:pointer;font-weight:600;
}

.scroll{flex:1;overflow-y:auto;overflow-x:hidden;padding:0 14px 16px;min-height:0;scrollbar-width:none}
.scroll::-webkit-scrollbar{width:0;height:0;display:none}
.scroll.flush{padding:10px 0 16px}
.scroll.home{display:flex;flex-direction:column;padding:0 14px 14px}

/* ---------------------------------------------------------- 深色站牌 */
.card{
  background:linear-gradient(168deg,#123A5C 0%,#0B2743 52%,#071A2D 100%);
  border-radius:26px;padding:22px 20px 16px;color:#fff;
  position:relative;overflow:hidden;cursor:pointer;
  box-shadow:inset 0 1px 0 rgba(255,255,255,.11),
             0 24px 50px -30px rgba(7,26,45,.95),
             0 3px 10px rgba(7,26,45,.16);
}
.card.up,.card.dn{background:linear-gradient(168deg,#123A5C 0%,#0B2743 52%,#071A2D 100%)}
.scroll.home .card{flex:1;min-height:0;display:flex;flex-direction:column}
.card::after{
  content:"";position:absolute;left:-54px;top:-124px;width:250px;height:250px;
  border-radius:50%;background:radial-gradient(circle,rgba(96,176,255,.14),transparent 68%);
  pointer-events:none;
}

.ctop{display:flex;align-items:center;gap:10px;position:relative;z-index:1}
.lineno{
  font-size:17px;font-weight:800;letter-spacing:-.2px;line-height:1.15;
  background:#fff;color:#0B2743;border-radius:9px;padding:5px 11px;
  flex-shrink:0;
}
.lineno.up,.lineno.dn{color:#0B2743}
.toward{
  font-size:14.5px;color:rgba(255,255,255,.74);flex:1;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
}
.swapbtn{
  margin-left:auto;flex-shrink:0;display:inline-flex;align-items:center;gap:6px;
  border:1px solid rgba(255,255,255,.26);background:rgba(255,255,255,.14);color:#fff;
  border-radius:999px;padding:7px 12px;
  font-size:12.5px;font-weight:600;font-family:inherit;
  cursor:pointer;line-height:1.2;white-space:nowrap;
}
.swapbtn .si{font-size:13px;color:rgba(255,255,255,.66)}
.swapbtn b{font-size:14.5px;font-weight:700;color:#FFD07A}

.cmid{margin-top:16px;position:relative;z-index:1}
.main{display:flex;align-items:flex-end;gap:5px}
.min{
  font-size:92px;font-weight:800;line-height:.82;letter-spacing:-5px;
  color:#fff;font-variant-numeric:tabular-nums;
}
.min.up,.min.dn{color:#fff}
.unit{font-size:22px;font-weight:600;color:rgba(255,255,255,.66);letter-spacing:0;padding-bottom:10px}
.unit.up,.unit.dn{color:rgba(255,255,255,.62)}
.stxt{
  font-size:44px;font-weight:800;line-height:1.05;letter-spacing:-1.5px;
  margin-top:12px;color:#fff;
}
.stxt.up,.stxt.dn{color:#fff}
.sub{font-size:16.5px;color:rgba(255,255,255,.68);margin-top:13px;line-height:1.5}
.sub b{font-weight:700;color:#fff}
.go{
  display:inline-block;background:#F5A524;color:#231500;
  border-radius:7px;padding:3px 9px;font-size:13.5px;font-weight:700;
  margin-right:7px;letter-spacing:0;
}

.swin{
  margin-top:15px;padding-top:13px;border-top:1px solid rgba(255,255,255,.13);
  position:relative;z-index:1;
  flex:1;min-height:0;display:flex;flex-direction:column;
}
.swabove{font-size:12.5px;color:rgba(255,255,255,.62);padding:0 0 5px;flex-shrink:0}
.swrow{
  position:relative;display:flex;align-items:center;gap:10px;
  flex:1;min-height:36px;padding-left:23px;
}
.swrow::before{
  content:"";position:absolute;left:4px;top:0;bottom:0;
  width:1.5px;background:rgba(255,255,255,.24);
}
.swrow:first-child::before{top:50%}
.swrow:last-child::before{bottom:50%}
.swrow .d{
  position:absolute;left:0;top:50%;transform:translateY(-50%);
  width:9px;height:9px;border-radius:50%;background:#0C2743;
  border:1.5px solid rgba(255,255,255,.32);box-sizing:border-box;
}
.swrow.mine .d{border:none;background:#fff;box-shadow:0 0 0 4px rgba(255,255,255,.17)}
.swrow.bus .d{border:none;background:#F5A524;box-shadow:0 0 0 4px rgba(245,165,36,.22)}
.swrow .n{
  font-size:17.5px;color:rgba(255,255,255,.76);flex:0 1 auto;letter-spacing:-.1px;
  max-width:68%;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
}
.swrow::after{content:"";flex:1 1 0;height:0}
.swrow.mine .n{font-weight:700;color:#fff}
.swrow .tb{
  font-size:11px;font-weight:700;color:#231500;background:#F5A524;
  border-radius:5px;padding:2px 7px;
}
.swrow .tm2{
  font-size:11px;font-weight:700;color:#0B2743;background:#fff;
  border-radius:5px;padding:2px 7px;
}

.cfoot{
  display:flex;align-items:center;margin-top:6px;padding-top:13px;
  border-top:1px solid rgba(255,255,255,.13);
  position:relative;z-index:1;flex-shrink:0;
}
.swall{
  font-size:15px;color:rgba(255,255,255,.92);font-weight:600;
  white-space:nowrap;display:inline-flex;align-items:center;gap:4px;
}

/* ---------------------------------------------------------- 列表 */
.sec{font-size:12.5px;color:#7B7E74;margin:14px 18px 8px;font-weight:600;letter-spacing:.3px}

#lst{background:#fff;border-radius:22px;margin:0 14px;overflow:hidden;
     box-shadow:0 1px 2px rgba(15,37,55,.05)}
#lst .row:last-child{border-bottom:none}

.panel{background:#fff;border-radius:22px;margin:10px 0;overflow:hidden;
       box-shadow:0 1px 2px rgba(15,37,55,.05)}
.panel .sec{margin:14px 16px 6px}
.panel .row{padding-left:16px;padding-right:16px}
.panel .row:last-child{border-bottom:none}

.row{
  display:flex;align-items:center;gap:12px;
  padding:18px 16px;background:#fff;border-bottom:1px solid #F2F3EC;cursor:pointer;
}
.row:active{background:#F7F8F2}
.row .ln{
  font-size:16px;font-weight:800;color:#fff;background:#123A5C;
  border-radius:8px;padding:5px 9px;min-width:70px;text-align:center;
  letter-spacing:-.2px;font-variant-numeric:tabular-nums;flex-shrink:0;
}
.row .dst{flex:1;font-size:15px;color:#6E7168;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.row .tm{
  font-size:24px;font-weight:800;color:#0B2743;text-align:right;
  white-space:nowrap;font-variant-numeric:tabular-nums;letter-spacing:-.8px;
  min-width:64px;
}
.row .tm.hot{color:#C2410C;font-size:18px;letter-spacing:0}
.row .tm.wait{font-size:15px;font-weight:500;color:#8E9188;letter-spacing:0}
.row .arrow{color:#C9CCC2;font-size:16px}
.row.first{border-top:none}
.srow .ln{
  background:none;color:#0B2743;padding:0;min-width:auto;
  margin-right:2px;font-size:17px;border-radius:0;text-align:left;
}

.more{
  margin:10px 14px 0;padding:17px;border-radius:16px;
  text-align:center;font-size:15.5px;color:#123A5C;cursor:pointer;
  font-weight:600;background:#fff;
  box-shadow:0 1px 2px rgba(15,37,55,.05);
}

/* ---------------------------------------------------------- 搜索 */
.sbar{display:flex;gap:9px;padding:2px 14px 14px;flex-shrink:0}
.sinput{
  flex:1;height:54px;border:1.5px solid #D8DACF;border-radius:17px;
  padding:0 16px;font-size:19px;font-family:inherit;outline:none;
  background:#fff;color:#111;
}
.sinput:focus{border-color:#123A5C;box-shadow:0 0 0 3px rgba(18,58,92,.09)}
.sbtn{
  width:78px;height:54px;border:none;border-radius:17px;background:#0B2743;color:#fff;
  font-size:17px;font-weight:600;font-family:inherit;cursor:pointer;
}

/* ---------------------------------------------------------- 线路头 */
.lhead{padding:2px 20px 14px;flex-shrink:0}
.lh1{display:flex;align-items:center;gap:12px}
.lh2{font-size:19px;font-weight:500;color:#5A6068;letter-spacing:-.1px}
.lh2 b{font-weight:700;color:#0F2537;font-size:21px}
.swap{
  margin-left:auto;flex-shrink:0;display:inline-flex;align-items:center;gap:5px;
  border:1px solid #CFD2C6;background:#fff;color:#123A5C;
  border-radius:999px;padding:9px 15px;
  font-size:13.5px;font-weight:600;font-family:inherit;cursor:pointer;line-height:1;
}
.lh3{font-size:12.5px;color:#7B7E74;margin-top:7px}
.noreal{
  background:#FDF4E3;color:#85571A;border-radius:10px;
  padding:10px 13px;font-size:13px;margin-top:10px;line-height:1.5;
}

/* ---------------------------------------------------------- 时间轴 */
.tl{
  position:relative;padding:16px 0 30px;
  background:#fff;border-radius:24px;margin:0 14px 14px;overflow:hidden;
  box-shadow:0 1px 2px rgba(15,37,55,.05);
}
.stop{display:flex;align-items:center;gap:13px;padding:0 16px;height:58px;position:relative}
.stop::after{content:"";flex:1 1 0;height:0}
.stop .rail{position:absolute;left:32.25px;top:0;bottom:0;width:1.5px;background:#E2E4D9}
.stop:first-child .rail{top:50%}
.stop:last-child .rail{bottom:50%}
.dot{
  position:relative;z-index:1;width:12px;height:12px;border-radius:50%;
  background:#fff;border:1.5px solid #C9CCBE;flex:0 0 12px;margin-left:11px;
  box-sizing:border-box;
}
.dot.mine{border:none;background:#123A5C;box-shadow:0 0 0 4px rgba(18,58,92,.16)}
.dot.bus{border:none;background:#E0761C;box-shadow:0 0 0 4px rgba(224,118,28,.17)}
.sname{
  font-size:19px;color:#2E3238;flex:0 1 auto;letter-spacing:-.2px;
  max-width:64%;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
}
.sname.mine{font-weight:700;color:#123A5C}
.tagme{font-size:11.5px;font-weight:700;color:#123A5C;background:#E8EFF6;border-radius:5px;padding:3px 7px}
.tagbus{font-size:11.5px;font-weight:700;color:#fff;background:#E0761C;border-radius:5px;padding:3px 7px}
.stop.mine{background:#F4F8FC;box-shadow:inset 3px 0 0 #123A5C}
.stop.busrow{background:#FFF9F1}
.stop.mine.busrow{background:#F4F8FC}
.busmeta{font-size:13px;color:#B0600E;margin-left:8px}

/* ---------------------------------------------------------- 底部按钮 */
.btnrow{display:flex;gap:9px;padding:10px 14px 18px;flex-shrink:0}
/* 底部留白躲开全面屏的手势条。先给普通值兜底，再用 max() 覆盖 ——
   env() 不被支持时整条声明会被丢掉，所以不能只写一条。 */
.btnrow{padding-bottom:max(18px, env(safe-area-inset-bottom))}
.btn{
  flex:1;height:60px;border:none;border-radius:19px;font-size:17px;
  font-weight:600;font-family:inherit;cursor:pointer;
  transition:transform .12s ease, filter .12s ease;
  -webkit-tap-highlight-color:transparent;
}
/* 手机上按下去必须有回应。老人点了没动静会以为没点中，接着连点三下 */
.btn:active{transform:scale(.975);filter:brightness(.96)}
.btn.p{background:#0B2743;color:#fff;box-shadow:0 10px 22px -14px rgba(11,39,67,.95)}
.btn.s{background:#fff;color:#2A3238;border:1px solid #DDDFD2}
.btn.on{background:#123A5C;color:#fff}
.tip{font-size:12px;color:#8E9188;text-align:center;padding:14px 0 4px}
.loading{padding:64px 20px;text-align:center;font-size:17px;color:#8A8D83}
.err{background:#FDF0EE;border:1px solid #EFC2B9;border-radius:16px;padding:20px;margin:16px 4px}
.err h3{font-size:19px;color:#A33224;margin-bottom:8px}
.err p{font-size:15px;color:#55595E;line-height:1.55}
"""

V2_OVERRIDE = r"""
/* ==================================================================
   V2 覆盖层：只写与 V1 的差异，便于逐条对照
   维度：布局结构 / 视觉层级 / 交互流程 / 一致性 / 响应式 / 无障碍
   ================================================================== */

/* ---- 响应式：字号跟随屏宽，360 小屏不再挤 ---- */
.min{font-size:clamp(66px,25vw,96px);letter-spacing:-.055em;line-height:.84}
.unit{font-size:clamp(16px,4.6vw,22px);padding-bottom:.10em}
.stxt{font-size:clamp(34px,12.5vw,48px)}
.lineno{font-size:clamp(23px,6vw,27px)}

/* ---- 布局：卡片分区更清楚 ---- */
.scroll.home{padding:0 14px 12px}
.card{border-radius:24px;padding:22px 20px 16px}

/* ---- 视觉层级：数字区重排，「还有 X 站」进入同一信息组 ---- */
.sub{
  font-size:16px;color:#5C6157;margin-top:12px;
  display:flex;align-items:center;gap:7px;flex-wrap:wrap;
}
.sub b{font-weight:700;color:#1A1C1E}
.go{margin-right:2px}

/* ---- 视觉层级：车位置提示降噪，改成列表的上下文而不是公告 ---- */
.swabove{
  display:flex;align-items:center;gap:7px;
  font-size:13.5px;color:#85897E;padding:0 0 9px;line-height:1.4;
}
.swabove::before{
  content:"";width:5px;height:5px;border-radius:50%;
  background:#C7CCBE;flex-shrink:0;
}

/* ---- 点站点看车多久到：选中行 + 顶部就地变成估算条 ---- */
.swrow{cursor:pointer}
.swrow[data-sel="1"]{background:#E8F0F7;border-radius:9px}
.swrow[data-sel="1"] .n{color:#0B4F8A;font-weight:700}
.swrow[data-sel="1"] .d{border-color:#0B4F8A}
.swabove.hot{
  display:flex;align-items:center;gap:7px;flex-wrap:wrap;
  background:#0E3A63;color:#fff;border-radius:11px;
  padding:9px 11px;margin:0 0 9px;font-size:14px;line-height:1.35;
}
.swabove.hot::before{display:none}
.swabove.hot .to{
  flex:1;min-width:0;font-weight:700;font-size:14.5px;color:#fff;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
}
.swabove.hot .t{font-size:16px;font-weight:700;color:#fff;flex-shrink:0}
.swabove.hot .x{color:rgba(255,255,255,.74);font-size:12.5px;flex-shrink:0}
.swabove.hot .bx{
  margin-left:auto;width:26px;height:26px;flex-shrink:0;padding:0;
  background:rgba(255,255,255,.18);border:0;border-radius:50%;
  color:#fff;font-size:16px;line-height:1;
}

/* ---- 交互：换方向更像按钮，不再像标签 ---- */
.swapbtn{
  border-color:#D5DAE1;color:#2F353C;
  box-shadow:0 1px 2px rgba(22,32,43,.06);
  padding:9px 13px;
}
.swapbtn:active{background:#F2F4F7}

/* ---- 交互 + 无障碍：响铃入口有足够触控高度和对比度 ---- */
.remlink{
  min-height:48px;padding:0;display:inline-flex;align-items:center;gap:5px;
  font-size:15px;font-weight:600;color:#0E3A63;
}
.remlink.on{color:#A8480B;font-weight:700}

/* ---- 一致性：三页导航同一套尺寸 ---- */
.nav{padding:18px 20px 12px;min-height:56px}
.back{padding:12px 12px 12px 0;margin:-12px 0}

/* ---- 站牌页：三列栅格，线路号/方向/时间严格对齐 ---- */
.row{
  display:grid;
  grid-template-columns:104px minmax(0,1fr) auto;
  align-items:center;column-gap:12px;
  padding:17px 2px;
}
.row .ln{min-width:0;font-size:20px;letter-spacing:-.3px}
.row .dst{min-width:0;font-size:15px;color:#6B7165}
.row .tm{min-width:54px;font-size:25px}
.row .arrow{display:none}
.srow{grid-template-columns:minmax(0,auto) minmax(0,1fr) auto}
.srow .ln{font-size:19px}

/* ---- 搜索结果里的站点行：站名占满整行，距离靠右，别用线路号那套 104px 窄列 ---- */
.strow{grid-template-columns:minmax(0,1fr) auto;column-gap:8px}
.strow .ln{
  font-size:19px;line-height:1.35;
  overflow-wrap:break-word;
}
.strow .dstop{font-size:14px;color:#8A8F94;white-space:nowrap}

/* ---- 站牌页：底部两块间距收紧 ---- */
.more{padding:19px 2px;font-size:15.5px}
.tip{font-size:12.5px;color:#7A7F74;padding:8px 0 2px}

/* ---- 详情页：顶部信息与列表分开 ---- */
.lhead{padding:2px 20px 15px;border-bottom:1px solid #EFEEE7}
.lh2{font-size:19px;font-weight:500;color:#4A4F45}
.lh2 b{font-size:21px;font-weight:700;color:#0E3A63}
.lh3{font-size:12.5px;color:#7A7F74}
.swap{border-color:#D5DAE1;box-shadow:0 1px 2px rgba(22,32,43,.06)}

/* ---- 详情页：时间轴加深一档，长列表不糊 ---- */
.tl{padding:14px 0 32px}
.stop .rail{background:#D5D4C9}
.stop{height:58px}
.sname{font-size:19.5px}
.tagme{background:#E3EDF9;color:#0E3A63}

/* ---- 无障碍：灰字统一提到 4.5:1 以上 ---- */
.sec{color:#7A7F74}
.nav .r{color:#6E7368}
.tip{color:#7A7F74}
.cfoot{padding-top:12px}

/* ---- 无障碍：键盘/读屏可见 ---- */
:focus-visible{outline:2.5px solid #0E3A63;outline-offset:2px;border-radius:8px}
.btn:focus-visible{outline-offset:3px}

/* ---- 按压反馈：白卡的 .btn 定义在 CSS_A 里，那里没有 :active，
   必须在这一层补，否则浅色版点了毫无反应（深色版 CSS_B 自带，所以之前
   只测深色会以为已经生效）。移动端 WebView 单靠 :active 常常不触发，
   真正的按压态由 JS 加 .down 类，这条是给桌面和部分 WebView 兜底。 ---- */
.btn{transition:transform .12s ease, filter .12s ease, background .12s ease}
.btn:active,.btn.down{transform:scale(.975);filter:brightness(.94)}
.btn.s:active,.btn.s.down{background:#E4E3DA}
.opt:active,.opt.down{transform:scale(.975)}
.th:active,.th.down{transform:scale(.96)}
#buildline{margin-top:10px;text-align:center;font-size:12.5px;color:#A0A49A}
.row:active,.row.down{background:#F1F1EA}
.swall:active,.swall.down{opacity:.55}

/* ---- 收藏星标：列表里一行一个，站牌页标题旁边一个 ---- */
.favtog{
  flex:0 0 auto;width:34px;height:34px;margin-left:2px;padding:0;
  border:0;border-radius:9px;background:transparent;cursor:pointer;
  font-size:18px;line-height:1;color:#C9CCC2;font-family:inherit;
  transition:transform .12s ease, color .12s ease;
}
.favtog.on{color:#E8A008}
.favtog:active,.favtog.down{transform:scale(.88)}
.favbtn{
  border:0;background:transparent;cursor:pointer;font-family:inherit;
  font-size:19px;line-height:1;color:#C9CCC2;padding:0 7px;
}
.favbtn.on{color:#E8A008}

/* ---- 附近站点：定位状态 + 范围三档 + 站点列表 ---- */
.nearhead{display:flex;align-items:baseline;justify-content:space-between;
          padding:14px 16px 0}
.nh{font-size:15.5px;font-weight:700;color:#1A1C1E}
.nstate{font-size:12.5px;color:#8A8F94}
.ranges{display:flex;gap:8px;padding:10px 16px 4px;flex-wrap:wrap}
.rg{
  flex:0 0 auto;padding:9px 15px;border-radius:12px;border:1px solid #E4E3DA;
  background:#fff;font-size:14px;color:#5C6166;font-family:inherit;cursor:pointer;
  transition:background .12s ease, color .12s ease, border-color .12s ease, transform .12s ease;
  min-height:38px;
}
.rg.sel{background:#0B2743;color:#fff;border-color:#0B2743;font-weight:600}
.rg:active,.rg.down{transform:scale(.95)}
/* 站名要黑 —— .row .dst 原本是给「往 某某」用的灰字，套到站点上老人看着费劲 */
.nitm .dst{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;
           color:#1A1C1E;font-size:16px}
.nitm .nd{font-size:13.5px;color:#8A8F94;flex-shrink:0;font-variant-numeric:tabular-nums}
/* 选中不只是换底色：左边一条竖线 + 站名加深，扫一眼就知道「现在看的是这站」 */
.nitm.sel{background:#E7EDF6;box-shadow:inset 3px 0 0 #0B2743}
.nitm.sel .dst{color:#0B2743;font-weight:700}
.nitm.sel .nd{color:#4A6B8F}
.nearnone{padding:12px 16px 6px;font-size:14px;color:#8A8F94;line-height:1.65}
/* 「这站有哪些车」的分段标题：要比 .sec 那层灰字重，
   否则整页会糊成一张长列表，老人分不清哪是站、哪是车 */
.curhead{
  margin:8px 16px 0;padding:18px 0 8px;border-top:1px solid #EFEEE8;
  font-size:16px;font-weight:700;color:#1A1C1E;letter-spacing:-.2px;
}

/* ---- 选线与列表：点得准，也看得出点中了 ----
   原来只有 :active 换个底色，桌面上鼠标移过去毫无反应，手机上按下去
   也只是一闪。这里补三件事：桌面悬停、按下位移、点击后先确认再跳。 ---- */
.row,.dircard{
  transition:background .12s ease, border-color .12s ease,
             box-shadow .12s ease, transform .12s ease;
}
.row .arrow{transition:transform .14s ease, color .14s ease}

@media (hover:hover) and (pointer:fine){
  .row:hover{background:#F7F7F1}
  .row:hover .arrow{transform:translateX(3px);color:#0E3A63}
  .dircard:hover{background:#FCFCF8;border-color:#DDDCD2;
                 box-shadow:0 6px 18px -12px rgba(22,32,43,.45)}
  .dircard:hover::after{color:#0E3A63;transform:translateY(-50%) translateX(3px)}
}

.row:active,.row.down{background:#EDEDE3;transform:scale(.994)}
.dircard:active,.dircard.down{background:#F5F5EE;transform:scale(.995)}
/* 点下去到跳转之间那 90ms，给个明确回答：这一下算数 */
.row.tapped{background:#E6ECF4}
.dircard.tapped{background:#EAF0F7;border-color:#C9D6E6}

/* 换页的进入动画。静默刷新不重建 DOM，所以它只在新页面出现时放一次，
   不会每 15 秒闪一下。滚动容器只淡入不位移 —— 带 transform 的滚动容器
   在部分安卓 WebView 上会滚不顺。 */
#app>.nav,#app>.btnrow{animation:appInY .16s ease-out both}
#app>.scroll{animation:appInO .16s ease-out both}
@keyframes appInY{from{opacity:.5;transform:translateY(5px)}to{opacity:1;transform:none}}
@keyframes appInO{from{opacity:.55}to{opacity:1}}

/* ---- 无障碍：尊重系统的「减少动态效果」 ---- */
@media (prefers-reduced-motion:reduce){
  *{animation-duration:.01ms !important;transition-duration:.01ms !important}
}

/* ---- 响应式：窄屏收一档，别把方向名截断成「浙南科…」 ---- */
@media (max-width:374px){
  .toward{font-size:13.5px}
  .swapbtn{font-size:11.5px;padding:8px 10px;gap:4px}
  .swapbtn b{font-size:13.5px}
}

/* ---- 响应式：极窄屏（320-359）再收一档 ---- */
@media (max-width:359px){
  .nav .t{font-size:21px}
  .row{grid-template-columns:92px minmax(0,1fr) auto}
  .row .ln{font-size:18px}
  .btn{font-size:16px;height:58px}
}

/* ---- 矮屏（老机型、或者浏览器地址栏占掉一大块）：把竖向空间抢回来给站点列表。
        不这么收的话，360×640 上列表只剩三行，等于没有。 ---- */
@media (max-height:700px){
  .min{font-size:clamp(52px,20vw,70px);letter-spacing:-3px}
  .cmid{margin-top:8px}
  .sub{margin-top:5px}
  .swin{margin-top:10px;padding-top:4px}
  .swabove{padding:1px 0 0}
  .swrow{height:44px}   /* 矮屏收到 44，正好是触控底线，再小就点不准了 */
  .cfoot{padding-top:8px}
  .btnrow{padding-top:8px;padding-bottom:max(12px, env(safe-area-inset-bottom))}
  .btn{height:58px}
}

/* ---------------------------------------------------------- 顶栏安全区 */
/* 刘海屏上标题会被状态栏压住。同样是先兜底再覆盖。 */
.nav{padding:20px 20px 13px;padding-top:max(20px, env(safe-area-inset-top))}

/* ---------------------------------------------------------- 设置面板：配色 */
/* 面板现在有响铃和配色两段，小屏（640 高）会顶到屏幕外，给它自己能滚 */
.sheet{max-height:90vh;overflow-y:auto;-webkit-overflow-scrolling:touch;
       scrollbar-width:none;
       padding-bottom:calc(22px + env(safe-area-inset-bottom, 0px))}
.sheet::-webkit-scrollbar{display:none}
.sheet .sect-t{
  font-size:13.5px;font-weight:600;color:#96998F;letter-spacing:.2px;
  margin:20px 2px 8px;padding-top:14px;border-top:1px solid #EFEEE7;
}
.sheet .sect-t:first-of-type{margin-top:18px;padding-top:0;border-top:0}
.themes{display:flex;gap:9px;margin-top:4px}
.th{
  flex:1;height:78px;border:1.5px solid #E2E1D9;border-radius:15px;background:#fff;
  font-family:inherit;cursor:pointer;padding:0;
  display:flex;flex-direction:column;align-items:center;justify-content:center;gap:3px;
}
.th i{width:22px;height:22px;border-radius:7px;display:block}
.th b{font-size:15px;font-weight:600;color:#2A2E33}
.th small{font-size:11.5px;font-weight:500;color:#8A8F94}
.th.sel{border-color:#0E3A63;background:#F4F8FC;box-shadow:inset 0 0 0 1px #0E3A63}
.th.sel b{color:#0E3A63}
.thhint{font-size:12.5px;color:#96998F;margin-top:10px;text-align:center}
.nav .setlink{
  font-size:14px;font-weight:600;font-family:inherit;cursor:pointer;
  color:#6B7076;background:#F2F1EA;border:none;border-radius:9px;padding:5px 11px;
}
"""

# ---------------------------------------------------------------- 两套新配色
#
# 只换颜色，不动布局、字号、间距 —— 所以 d / e 和现在的白卡长得一模一样，
# 变的只是冷暖。一次性正则替换 hex，避免映射之间互相踩（A→B 之后又被 B→C 换掉）。
#
# d 暖橘：底色暖白，主色深橘棕。和暖橘图标同色系，最亲和。
# e 晴空：底色冷白，主色亮蓝，橙黄作点缀。清爽但有活力，和晴空图标同色系。

import re as _re

_THEME_WARM = {
    # 品牌深蓝系 → 暖橘棕系
    "#0E3A63": "#A8461C", "#123A5C": "#8F3A16", "#0B2743": "#5C2410",
    "#0F2537": "#6B2C13", "#071A2D": "#3D1808", "#0B4F8A": "#C25A2A",
    # 正文与深灰
    "#1A1C1E": "#2B2320", "#16202B": "#3A2A20", "#2A2E33": "#3E3128",
    "#2E3238": "#463830", "#3A4048": "#52443A", "#3C4046": "#564840",
    "#55595E": "#6B5B50",
    # 次要文字
    "#6B7076": "#7D6C60", "#7A7F74": "#857467", "#8A8F94": "#9A8A7D",
    "#96998F": "#A2948A", "#7B7E74": "#87766A", "#8E9188": "#9B8D82",
    # 背景与边框
    "#FAFAF7": "#FFF8F1", "#EFEEE7": "#F7ECE1", "#F0EFE8": "#F8EDE3",
    "#EAE9E2": "#EFE2D5", "#DFE3E8": "#E8D9CB", "#CFCEC5": "#DCCBBC",
    "#D5DAE1": "#E2D3C4",
    # 提醒与紧急（往红偏，和主色的橘区分开）
    "#DA6B1C": "#C0392B", "#F5A524": "#E8A33D", "#C2410C": "#A72E20",
    "#A8480B": "#8F2A18", "#B4550E": "#9E2F1C", "#B0600E": "#A53A22",
    "#E0761C": "#C93A2A", "#231500": "#2B1A12",
    # 状态色与浅底
    "#1F9E5A": "#2C8C6E", "#A33224": "#A72E20",
    "#FDF0E3": "#FDF1E4", "#FDF0EE": "#FDF0EC",
    "#EAF1F8": "#FBF1E7", "#F4F8FC": "#FDF5ED",
    "#E8F0F7": "#FBEEE4",
}

_THEME_SKY = {
    "#0E3A63": "#1B5FB0", "#123A5C": "#17549C", "#0B2743": "#0E3A6B",
    "#0F2537": "#113F73", "#071A2D": "#0A2C52", "#0B4F8A": "#2C7BE5",
    "#1A1C1E": "#16202B", "#2A2E33": "#26313D",
    "#2E3238": "#2B3642", "#3A4048": "#37434F", "#3C4046": "#394552",
    "#55595E": "#55636F",
    "#6B7076": "#6E7B87", "#7A7F74": "#7C8794", "#8A8F94": "#8A97A3",
    "#96998F": "#97A3AE", "#7B7E74": "#7E8A96", "#8E9188": "#949FAA",
    "#FAFAF7": "#F6FAFF", "#EFEEE7": "#EEF4FB", "#F0EFE8": "#EFF5FC",
    "#EAE9E2": "#DFE9F4", "#DFE3E8": "#D8E3EF", "#CFCEC5": "#CBD8E6",
    "#D5DAE1": "#D3DFEC",
    "#DA6B1C": "#E8734A", "#F5A524": "#F5A63C", "#C2410C": "#C9452B",
    "#A8480B": "#A83C22", "#B4550E": "#B84A2A", "#B0600E": "#B0553A",
    "#E0761C": "#E4784F", "#231500": "#26201A",
    "#1F9E5A": "#17A673", "#A33224": "#B03A2C",
    "#FDF0E3": "#FFF4E8", "#FDF0EE": "#FFF2EE",
    "#EAF1F8": "#E9F2FD", "#F4F8FC": "#F1F7FE",
    "#E8F0F7": "#E6F0FC",
}


def _tint(css, mapping):
    return _re.sub(r"#[0-9A-Fa-f]{6}",
                   lambda m: mapping.get(m.group(0).upper(), m.group(0)), css)


_BASE = CSS_A + V2_OVERRIDE

SKINS = {
    "a": CSS_A,
    "b": CSS_B,
    "c": _BASE,                       # 现有白卡（深蓝）
    "d": _tint(_BASE, _THEME_WARM),   # 暖橘
    # 晴空版：响铃入口单独用暖色点缀，别跟着主色一起变蓝，否则提醒就藏起来了
    "e": _tint(_BASE, _THEME_SKY) + "\n.remlink{color:#C9452B}\n",
}

# 用户能在「设置 → 手机配色」里选的三套。顺序就是面板里显示的顺序。
THEME_CHOICES = (
    ("c", "深蓝", "跟原来一样"),
    ("d", "暖橘", "看着暖和"),
    ("e", "晴空", "清爽明亮"),
)
