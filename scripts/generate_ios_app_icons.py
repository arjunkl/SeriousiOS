#!/usr/bin/env python3
"""Generate opaque iPhone app-icon PNGs from compact indexed artwork data."""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
from pathlib import Path
import struct
import zlib

SPECS = {
    120: {
        "palette": [(255, 255, 255), (250, 245, 184), (255, 241, 0), (255, 230, 0), (254, 230, 0), (253, 230, 0), (254, 229, 0), (252, 227, 4), (229, 196, 46), (180, 133, 46), (138, 65, 30), (231, 33, 39), (223, 33, 38), (223, 31, 38), (223, 31, 37), (212, 31, 37), (220, 24, 39), (111, 16, 19), (9, 7, 4), (4, 2, 1), (2, 1, 1), (2, 0, 0), (0, 0, 1), (0, 0, 0)],
        "indices_b85": (
            'c-p<2i+1Cx4u%saHU@l&0oU*UrbiNBgdwTj$v$3t&*~&?zUqSb5t?nQKXzMsv#s?v*Uc>3`sU4lcvj~;*E#1u-R1AEi(a<v`(Ol_'
            'UV+uo`rO<_PkJ$51_M&UXWCw_^p(R`Oy=cj949@08SGZmOXuK^P4(bxYd0m0bBU|;_@96wwsKoUZ={guV?|bTFOUBP7?Mi$%JlsL'
            '{{eL|9J|^X%_Z>k?X(7{0%L_-l*IhP=U^^A!-uq9FaAbW%EeeEdVFLr(BxxMrAI4MF?n6DyTK~tEwb<L_x|2PXbpH;DMd?pU89$y'
            'ujggWjEhWT7JDtLR4;@;><!2gOh((KvS6&`UJhU&+rZnI%QDYeUr0L#fiy;uwYM9B0V%=YSUrQa!;q8BZX4LCfT`j2<yyMqPs*Ju'
            'y}KaEF{dWa8(y!0M_G^a;-7gQ2|8ZlT0-{dTIAlP#J@>ny(gD3VzqoRlL4dmXPlxR&T_FRQxf;cyWat8$a=H-?IHws7zfeF*Er;n'
            'riXiBKAqK=x){Tk#Kh|FF2)VXu!ejx53jxvO@9O*pR4t3(L-3eP@PSPn_Zm^H3PidbkDBohu3HD1+ImJUUc8<QH!2Rm4cAXChQoY'
            'Mhf5pSo{LMvXF57Y7O}c=4t^yY33P=A;ex`0%$N-B9_29%dWV@;!9T+5|)kO1wRd*9(p-rVqqn8?tU}0fM0`n5*NTv`O3)1e7#;*'
            '6PorwIqLyJ*n`pFZ>oa+joTeUY-UI*j|K1(gAC;OAajs%xNI*<3yL9p#t7WSxHU>Fc~hkKb}WFwWXOeAd<NZ%u4zKt^?bfULk;%1'
            '1E2AdecE|Jfq<u-HG$i<UE7k$4P+n|3|RM~X&P|9j`?;zu~rur>4;SqDuzqaR^3p3s0Ox;u6y9qb@+9Iv?u-9b-2Q$=Uxdg76)H)'
            '7gK2JJ9%0np=p8G(pL|FcSuAirCT5D)$<i@tTh{z3Kn~3Zs6%3P<#r-kHHcO<s6;c2^RE5><MnpmdX{Es4sDAWsQNb+_s<W)gJ>Q'
            '0jw4&%VR;g;Ame9!9li~?cQ$Kq#Zq|yBuxwQY11<tkanlYVez1)Y-aLpe+T+v7X4tg{5@P)9Xg*4354c%?J&0yCIVyz>!OyUeBlV'
            'WsyRzFfy8)9DNR)<gvbd7(g;OTkw@c;PrPh9)6~4k;zsXC>8*B4>2TB;Me5G4_jB0Wa9FN(~m`8i`-y5&zR3A2zCmA-N+oy+vmX6'
            'gEa$V&GqH4&h|wkJTK8(dzlNq{sAz0nu!tAn~3&Dj#@HDF8q{e)b=N^L-0Wbk<y)_*~i$V!w;z$@fS~H9f!S=RM41-Y+}#eYL-%n'
            'O-D@9s#K2u(y0&#e#$W?quE2YP~fX|nK%}-YS-olJNJ1F@h(&Yy5QLe>19xMklWV@;g{@yiRN~P0K4sj*KPJDsRL9&phfg6*M3n|'
            'Bh><xA22DpP~LM8C`;?!77SB_81>hqd3vJ{<|5S~HB-PZ4L{Si+{-9)?#ouqa4e80b6w_XFFw%dwr8uE%&k+w+9!BfatP=fIGAE*'
            '$5o8QL+c?ZGU`r5@8v5-*Bm_zRNVu%eF~EyoI&tiZMm~yH*o5P*!;UU(<bTD?rS-0H@IR8>Jwu7JecbPOlNV!oef_tckhVfVoC-x'
            'b5$@mZ<CO%NPV`?)*L<R!$=I9T)cas=;$`3?%5X+E6A{OY2m4)RmxSvG2z*Nk@A~uzn|Z@>?zt{xOf5;zqwkRlUp6F7Fjs{u!b|a'
            'm1+iS`%(Mg8L^LgZAKwQFnkx67TIoUl?*fM**-H7Fzq5H3aY(YL~|={_Rb`-x0k-ysD@X_!O=Xc*!f}Ids3k~61TbsIxJa*Qyr`@'
            'eAShXmR@Y>!p()o7}{v>Qn8nkh_7J05HJ!uPWSTrF~A*n^MSka-QIh;5?(-HTyK;}yH`W0!lwufZikO9lUkWZW$Fe~>)~VK$~th1'
            '&)qq8D2|UR0^qmd#62{4GEYmN3$px>+pR!QM&C*|#GfJEu^(E7BX><X?F}xAWJb8fcd^@Y`(UulxJ5&Y<+L}rOlQm745s;5vgp>h'
            'l+c`eJRO3;iL0MorCL?FutYy|RnFCgy_P9SN`}&BOEtdyw>d6>!0ofc;r7<ieT|!$wr5b5ZN)+g+|+fba;IOoES9N8xRh@9%D(A$'
            'hO`U*mRPki8TLThe;oI}|8=CP6fA#KlCO6i%QIXm&q}F7DTc3?^3|Q&QQvkKlj;MPl(VdCsWGUo_G(4p2C4I5C6)1&RgLaK|K`lA'
            '_`CRxkZr&RgEQGd#r$tavdX@Y>$*dP6W2HK+s9QdY*%Gk?aGd)G(VLkT^Y9i?$X)Ux%w$02(0J3+L7vH+z9K5^@eHb=1HpKj?EQx'
            'HMO{#!^YqAC;CW%iEYAr+N6%*4K2&D@N}j)L=?S?v!8ki@kSVL6YtsPxQjrQPDqbrFcY(dxm8C~7u2^z<GE#t%nEmRGaZ8^Z#aZb'
            '!>*x+-CR;w@6Y!Jt(1HZEVv+nNR0>TD?jnSGq+T-*nIZS{eC|XYuu2{;9;T1>`HIKn_+Hlif+g(ZZO{Pe8lG5U@jD(yt(2#S*9>o'
            'uy+01CG6;mSRVL?W4iMF!htt85|y8jux8+u$bL<5IC$HbSSiekB^Kv;bFp5$4maa?jlHhLU<4ex<C*Y%zb>@+U7po4JB~{)amFFP'
            'kKY@GEV};SEd?6=EE+3s>P8S+kl(CcQE8@)cVO4S(bQrN#5Wr7vW>`?TGpMdl!rBhT-L=I=st=!>SjIX*Qj9hfIW^YRT_iuN-wA0'
            '_q1f4SWvKw&RQ#}r_*&8x20n)CvyilaNA?K_YJJ+NXGpTLcClCBeuopvQ~fPQ`UE6=})g$!H`qf6YcVyz}7Am;QwRS4#E8&z&M%L'
            '`lBqD&GoAVdbQHI6CSKK>rN|=O?m9QV}8wOAoI(5I-+4^SKCRG?e?R>;^$4Pk9Tj8JdKAo3#wYPom$9vi*vjLK5-#b^!l|IJ)#k6'
            '`;F|-SP?fCuBc8ZCJRRqZgJQbp>$&7^F4XB;d)R!kKA+91uIUdOhrEnmm`uvCA&8=*2s46GV*jjdGD5AA~F5(K=KbY?9%+I3-!^`'
            '#dB&nC+_L{J~p}+GCF(`klS7voAyGtZ^PI<#wmwxA1~Oitxn%FG651){7$C30vvlYar?u~*AEuZAccP(nP5JB)y@>iDA+AQhvOPF'
            'tsw-ChT)(HGSSpDJ%X>Inv2-;(@<P-g%ym-J3d0BzdRn`gckme<2-3xX3%m^t1H}?TBP(koP~L!g)|H!@cN<Up`@!o6pitrft_?L'
            'xiCBuC+VPaG~R`~IivQXfTb>p#(W$q4Pl+1S)qaMJ+Xv$;mC%awBR#Ixo9k>>@IM#Cj84!SQVlmVLuG`UA(SmW3a<e%(6iM_d<qk'
            'u@6&r*SNgDQ~R_bR?x$J`Zu`Kr%^!y(}_T5SRAqOQ={WF{gb`#!076{$?Na%=kUa#)r(wnFt?aO1soLRKAV;p=TJdcoXx@^-Raug'
            '3*VHI@A%ZM2eVY3^cZIqc2#2$Z?1^ZFqX9YPQ@u>Mjo=Xi_<XS)V2O)*4zhpCMHfcv#IKZ%>fJvtA}NKGw8lv<)Wb~Ok1!ia<hy@'
            'uESaHJO82p1H3FI&eZU!`7P6ayN~VmrDuIJ$FtH|E=%p{tN(E0ZEV&pFDrWap0&T}>;#_vZ`cg{xB0Mth=B)Bf0>8-C$Ocg{`$W{'
            'I#o*NE2GBW1dq%A8yjlNAF=-fO?KB}'
        ),
    },
    180: {
        "palette": [(255, 255, 255), (250, 246, 174), (255, 240, 0), (255, 230, 0), (254, 230, 0), (253, 230, 0), (252, 227, 6), (225, 188, 45), (155, 94, 35), (208, 35, 36), (229, 32, 39), (223, 32, 38), (223, 31, 39), (223, 31, 38), (223, 31, 37), (214, 31, 37), (221, 24, 39), (128, 18, 22), (11, 7, 4), (3, 2, 1), (2, 1, 1), (2, 0, 0), (0, 0, 1), (0, 0, 0)],
        "indices_b85": (
            'c-qyS>w2TQ4u%sF4#nYQn{fYkx+U2LpCN&1_u@y}Y4c>>h|jVt$!1v&Tyo)cE#~FWH4DDX2VeUSFJk8K?FjNRb<-b16Q~qTJuL!='
            '<SsIASv!ek{!3(}6iZVz$h=s_j^WQU|7nN5o%mlub14n8l#=sJwh3jlL)Q)M&!0gH5Hi|VEE5VEzctFf0yG|CA#&e!e+o^kAY`Ei'
            'A$+N|M3%V;M<pqv>lAeVchC(%bNbd4%GyE*j{lZ%Wzf~X+COq1vjC4l7Oud;@TCTQgQ26o4}3;vUw;J+!>&fY2ACB%5_386MJyRJ'
            'ld0Qj{&jswA!d?t%_oq>R8=+Sq!S)-b?BOV$IyS_^U#tY-3p=6#zh6TZph?9YEE|my3E>r{2nzpv!+3R%yH;}ZR`3D-{5ERB%pKw'
            ';B!(L#(hl70aMR-UE=3J3v~mx7Ytn0x9WbcYqI$gnF~P~eHUJRNBWp|c&~C9GoQ%1fZg2h)x8Gh8~h8r2uQktzc!nXo@Ws#!-)C^'
            '!;b`){ypc@Rnq5VSCR!?H&iw7R(J<${4$v-CZ-Id526mSE#9BDMbCJFI?zQ_6$k@FalgTZ+(o57M+36q(wnrqxT%4f8`+wR{tM09'
            ';&8pf%oupipo502d{fXHuW;Plz`FF+6ZOR1w@2O%czgP^ui>mXz%?r-j;aPr-xM?Qaz5*q$azJ!%*+^zQnv$gt7`(@0qxuO>&>`A'
            '(1=T;urhWgZICY!uFG(cU*pK4#zv#IuYOQJ0IxS|o?{jy34K)sViR&hzs4chtaJA)r`|>$S=Ek=B}B6R&<8{H6f>>=^iadE4O$vS'
            '-Q1?-4fY3ei&;1>gN=1j)MJ;^cYL6pXKrwu0dPD1psz#f8>mHay#QZ57rAB!xq1Thi+#%cBTi{!R*NV;jG#?GF3>~Q_r{q31rHq^'
            '8{6^;S5dR^L+A^ZHt0DxGAKclRvN&>Ay4Ceo4G*I1{%%$B<Si>=+n*)SFUJ3M23rzsq1DIGap)YX?H8gaj@0Q3K^l>523Gcc685S'
            '5Vj+d7p;ouAW9wvihS^Ykiwq1S;s2Ftf1Mi4Z=0DLpygP+;Gqa>bj-HH%@BnAjDAGEM8Y-DCp-$&{r^nJeqdw&}$)Xg~rCQ4SXiN'
            'gq7F*hPGG3&<wzhx*oIoaAwTmJTq7iRwQ63#+0aunckP1Fdl>gGYwf9Ls8evtNUOnUe?(k37p-@KpITg)Iao=fKtJjL#GE?!GW^A'
            'w^*9ntsz76)*65tbcLo4uodsfU@B+VIXhfhapl6$&M*!Uz4lfeQh+#aT&sgs&)|CCP$X>T*cW)wiB`;>Ft3P`^wNWkW2YrDh2s>|'
            '0Wsh#`A=0mBUb^`@DA!d2zPuDFI>;3<q)qJgkqhO$wm-O!dlSJ=C0}xxNLkr6VxCph1-E1YM9)C7sqRHEi*{eiX-|L$W5ibyy=qE'
            'Atn4!7iAn86jJE*O||iA&teN&T*}-Iu%_dYTqqg(u9Bz3T)LNSZY2lL8`|UZte`2BUzedc_Tou?A@5opGlX<y`FIr8_3*$0zhVu-'
            '^Bx+RU*@K%%!&~4BsDr|%suiFC`$^t@ggY@d4{`n#KF(GXmq(I!I@2~*u#((<FH_SzZX~?2u|w*@)3_Xwmk^Xk3tg`;~Qn)35VgG'
            'Y8VnYwaXDIH-^{yjY*t}utVnBoeISz%rG)`ZWz@m<jN|oI+3K`AUI%`D3ToWX+y8f`*E#Y7O|gs0PHHDhCyhr!cHpM*2cUWogA2<'
            'B<5IapV|@hNkd!i`I=Okayv-<DAOML6!hjc&buH>BuHJ^ruLX&^7?*au`-?gRfb-v3u~4yThGwnhotkeC6uqprCHRIWoqBh-xoA+'
            '7VNH@pnPgDwNbSfL!W?lli(N$$mP0AEbpc?`Y8OQLf`gO8u+|2VFh&;B_BLfR~kAnG-iH(__BOhXz>&G_$Km7OH=*dK-a<QyvIm#'
            '{s=oL>A+&Jd5h&AL6@<VlU>mG#>|v$;mhUFje-u<p~`e?LE`{6s5vM?RYh&8ua`kfVW6W4YpM(kn9_8T$El)SU}jd8MRT#C0ouqT'
            'm1S224K#ON+;dp$!*okoR{V14#eyDF^$e^Z^*<Azmn^bZ?VzkyS=8cU=4Eqvl(1&WVjY;fL+m+DEF#F1BKimFKxn<_qJ&dAkJ=A?'
            'qE-vP!fvxJVrI+&T(1tw<&-)JLMgTkb}V`#BljV)PKB36b@9YP(C=oQ#fdtF9SJXSRL&F3*g@gi<Y>!cikMk`;sGPCm2#cMRho>A'
            '<11Rr_2UN=x4?RNSZdd5PRLpHIUZlAh*&+r3a62}Rawn^F%F425l4`_aaBfWCW%Rm<&Zz2aGz%-?O|u6kt0TAql}1|sXBpmLvdiR'
            'E%@5VD2Az}dX`>J60p-|R>VVsn2j%k9P`eUL%I=(*pKt^rA<^FO^{M8yb7abW<}h$uV|MG7`fG%@G=@BQL>Iu#F86}xSmq|6wxse'
            '$pcqjgz7An_=IgL(JD<hvbr?LwTx#NH4B(JDG*_d49HPu88x&MpjtW8nTY!Yao4WphB6h3$_*zW5Q!_PoB3cek@E8m?Zu~-nX!*A'
            'PK?F*s@Ra@W?sh@5j8Of?EQUjHaw8Xi?(a|#Hs0I^I^>@5bvYevd9cn8MqF21Tss_(Y82-1#X)d&77OHZ7_E%ZeuT}_n42a$5f5h'
            '%5d59o*8)?^G-zPvN_AALw<$gJKNBu*Gj>&ZJumw{X!qS+g?B?Z4H=PA{T4yiM?6U9)*FL=Q*>&rYO#HJBOluZ1Hzpu%2*^&6BP;'
            '@)=$?$>lYU9F>MU7VpwwZVtsGxMJDLhLxAY^CP-oDdqPE9Fhj+#PwJ-E=C0-YV1j|7qZ&o*sWLuk~YDo?KN`gI;qVl#Nvi-SZKkq'
            'r+LNBDBQ$R?Ir&sl6DOZ(s*ax6oO)n7VxAKB1=+?SX9+*+3|L37#-x%V_RYT7F9M@#Zft<9;h|*-c0x}$CyAYadtOtkeT;^msO8w'
            '0xz2SkEFWnVfe_&Sr~6&V$yI?&}@IteRwI?q+{!abg?~W5lL_Azy(TD&c>gmpjF?&b~U+AZv>r;oU`d>dl+JTlt$*an+xp@H19Lz'
            'pjYOidUXeyt8#|U$yti~EyolfQ?JL)AoS#%Y&V!^&(Pa!m|>>Y9-qm6u?RlXE%RnN<T%Xi@8a1Eon;Qp=r9G+A@#@|$8nT-!ThZs'
            'D(%M3p)`Ev@H5>~16rCS>EY6BG_}7wbMvp5MSk`^&K$Z9<)h0-#ec=li+D$wyL5x2Z|F7U^+>ztFZH~~T)h}O)Xfcs_Qj!cULP{M'
            'euE$P8!PiO==V-C`%#C<IzMvL;5YtR>}7QezidAx#UXq_A7I{{2j%^!nc)w0bW+LmHH3n0i=8nT%qnN%jZGW=G9@EuZ~i{Sd|_O-'
            '$oINZX+QALG3K3>6-3M?evYOv*7*6BkDs?W<-=KJh&kv?4$0IT)^$o^ZF^vyLUXsVb5Km?sgNVZ-0ZfZt)+*AcaaAwFV;fku%Scd'
            'x;UCCkWMRL;sr-ah4FM9Q1fIA-G9k^O{LJP1sycBUzs-xS<E6WzryUK8GYBmqiaGpNW$GFkKOg)rOfG!U80T4-=V#&z02~tl5tw~'
            'maB^`zN3+UO3qgbT8M)QyT~x?`^+IFtC_8wj6Bb*JR;}vVAeb`48^=BXKUeoTF?d<X3P&tDtqei!e=MX2s7a<&hQfOq%vR$W_uRg'
            'GP>SA-+W5fNi%*gXx(LwXH1wa;)!>1EA>%B`*Ae3df9cN7popeOF&8M>TT^)V}+wh=66umeE9y(n_0YxJILlvhYh{;@RNWWFXm4$'
            'J6#-RcUkR6N{*BER^4INyh$&;y~|_~a1(gADo-){($LK(xsB^NHB$_IysJlTS-(ecv&^#g8c$ffql#zD{5Vtv!gzktyQgXI&pip7'
            'WfsyZ531dJU5t3Z^Un^MIo&=LO}c!;Y&mBj?&8FKzi!bE%=}`(_Qj;4xjCJ}nE4w!W2cOcor`CkvN4_FF(;?(V8>;=8!7P_KGySQ'
            'X6y{?5+?4Zt^M3LGdAHqp9c*s<8DI@#R&O5-fg4JoY<&5Y~9ca-;B}-4UMit9Cpw8o(R;;eV6&2?I{N0j);@K8KGZoT^v?)j$PF<'
            '?WrZgY!@X$<N<r2RV#6}c-#dY92oh3(`hbkaFj~Oyf*g4+RcZq)h3>^WmwvTO*^nlzwzX|PV*HU4IV_b+W>4Mdl3d#6e%;WJyf2t'
            '&#hOa5F(i(D5Kjade+8>!{v5h?4tN4R65GNwS0x!RKUp5K7KsiuTLM`K*lZ}oA0<d)iK*X!$(f-VM1xNIcn^vs*3Le>4Qm)hi~TW'
            '2Dh0{UHj@Y*dw!+;O{GUe2|-qn|W_f9(Cn*Ly~%Q^9J%dWWH{p4xC07S@#lm@zz{z>VIKrXQSBb!(*wCdRE5ncc9DbENvl2Qe9$q'
            'ztXIXO?}WupvASw;S&4U-aq<WnSOH<?IHC0w9Au%c9_N!U76}y!r0NB2u{wiXwLd+0e-pMHcb~*ev8Dev2p(di|wDVvSE07h&-bU'
            '(G<^gujPkF_{_AkW(a$X?c<MN*)lC(n_8&7Vda&_7N{Leea6tw@=-MWyP-%unqC6N9fIteE#7LUSX$9a)b;fKLLh2W`lG!57!KNz'
            'm)Li;>Z52<HNjjl(cAnV&Vpa>+mAwfS-cWY{aubLgsPiU?Hic_B%8TEvHL%4*!7YKplVGm4*;VoraE$Ph_|XbbBI=~CDZ%wz|@L*'
            '2OE!)jvl`e>32SR28UOf?IH;#qMj6Xv>0ph{IO$B;-|`-Vh;PN>PWVxd?@U<$?OM78af51ND*JkoT<Ng)Oavbg$KOyxAzurN+?z8'
            'kR<y+s>k!0s1%<(8^K%P#xi*;HXZ7v4<@w|kLm<91zbMq&?j}32K`xiQQb*qcmGP7Ss(PJ&&^U;Ww{-nrM=9vs#`i??ZsG&2eqj)'
            '%N%BQ_Rvn((0<KgyVp;3r_I4+54yZ#$_hF|6L=|A`x@7?;cDju)zjw%y1lP%%CuCp>P|oHGt+`I)sVPU<p#Yym#K>mwHrro3)|VF'
            '%7k0BSO=k&FWhRn)KPkm^a*Npbjvw2>_=KHzw^;_gl|c5ptJu*b+6TpeqpLCi98-WZ1kGr0$X<wk{%TAY9@1^S(pP}<F<pxqh5Z*'
            'A)b$F49tR!<4(@$OXMrgMh)kcmp1TT&M8^9{&i-ij|e@Gb4s=8{01}kb|>U7=1=gSAzyM**WTg#d(epd+sr|a@n_K9p?bf?oP97u'
            'V*CA;3Q3H=elXdp-aGjIvh%h-J5PP9KF3{#d8|PDdg+tKt<Nz04KoE(1?8K@*x?`QIS!L~jKlQvGpy*{&n3*f`}iX0Dl-0}&&yc!'
            'BPi&Z8K+OpjdZaEk6-Acc~pcB>#FhRl4wZ5FMIgQEd4|n9sEQ062c?;0iS#kZf*DXZ1i3F`7iUO4?A*0JH^}mOh%A&S0jZDnB+Yx'
            '4|KY58g9N0-5P{_&-D3Qt{_FMu;EYf{VzT`3OjatG%$`3>zp%Jk5sbD`j_^b6AQm)#+gtHf=&tx?%=FT1exmSFF(JH1Z@N{r=R<@'
            'EU{es-#l^-#G#*AH19lKD|TAg7DfF2Q}T`sY5a6C=qrzcy^>c$&(Y_$P0QauGd7=V9|B}K{~t3)p!;i&uKh<k@}c?i|BXytSq}97'
            'x0vl*`|#fwe{T3Xtlhu!e}Q>}?*H&H!rx>V0J?97{|xeK>GnT_tfBkqzl5xy{{`~@0DDWKSp'
        ),
    },
}

EXPECTED_SHA256 = {
    120: "689a9486c1193536350f12c95c2375cc19682107f6b640b4829f65d7ce0fba9c",
    180: "a5888eb1a5f02a0aed3b86ca909dd63c8ac1bcc8c0c550da81b5a1bba68a7c8d",
}


def png_chunk(kind: bytes, payload: bytes) -> bytes:
    crc = binascii.crc32(kind + payload) & 0xFFFFFFFF
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", crc)


def render_png(size: int) -> bytes:
    spec = SPECS[size]
    palette = spec["palette"]
    indices = zlib.decompress(base64.b85decode(spec["indices_b85"].encode("ascii")))
    expected_pixels = size * size
    if len(indices) != expected_pixels:
        raise RuntimeError(
            f"{size}px icon index count mismatch: expected {expected_pixels}, got {len(indices)}"
        )

    scanlines = bytearray()
    for row in range(size):
        scanlines.append(0)
        offset = row * size
        for column in range(size):
            index = indices[offset + column]
            try:
                red, green, blue = palette[index]
            except IndexError as error:
                raise RuntimeError(
                    f"{size}px icon palette index {index} is out of range"
                ) from error
            scanlines.extend((red, green, blue))

    signature = b"\x89PNG\r\n\x1a\n"
    header = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)
    return (
        signature
        + png_chunk(b"IHDR", header)
        + png_chunk(b"IDAT", zlib.compress(bytes(scanlines), 9))
        + png_chunk(b"IEND", b"")
    )


def write_icon(destination: Path, size: int) -> None:
    data = render_png(size)
    digest = hashlib.sha256(data).hexdigest()
    expected = EXPECTED_SHA256[size]
    if digest != expected:
        raise RuntimeError(
            f"{size}px icon hash mismatch: expected {expected}, got {digest}"
        )
    destination.write_bytes(data)
    print(
        f"app_icon={destination} size={size}x{size} mode=RGB alpha=no "
        f"bytes={len(data)} sha256={digest}"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("app_bundle", type=Path)
    args = parser.parse_args()
    app_bundle = args.app_bundle.resolve()
    if not app_bundle.is_dir():
        raise SystemExit(f"app bundle does not exist: {app_bundle}")

    write_icon(app_bundle / "Icon-60@2x.png", 120)
    write_icon(app_bundle / "Icon-60@3x.png", 180)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
