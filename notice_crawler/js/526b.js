
const {BigInteger: i} = require('./f33e')
    , {encodeDer: r, decodeDer: a} = require("./f99d")
    , o = require("./dffd")
    , s = require("./41d0").sm3
    , {G: l, curve: c, n: u} = o.generateEcparam();
function d(e, t, n="1234567812345678") {
    n = o.utf8ToHex(n);
    const i = o.leftPad(l.curve.a.toBigInteger().toRadix(16), 64)
        , r = o.leftPad(l.curve.b.toBigInteger().toRadix(16), 64)
        , a = o.leftPad(l.getX().toBigInteger().toRadix(16), 64)
        , c = o.leftPad(l.getY().toBigInteger().toRadix(16), 64);
    let u, d;
    if (128 === t.length)
        u = t.substr(0, 64),
        d = t.substr(64, 64);
    else {
        const e = l.curve.decodePointHex(t);
        u = o.leftPad(e.getX().toBigInteger().toRadix(16), 64),
        d = o.leftPad(e.getY().toBigInteger().toRadix(16), 64)
    }
    const h = o.hexToArray(n + i + r + a + c + u + d)
        , f = 4 * n.length;
    h.unshift(255 & f),
    h.unshift(f >> 8 & 255);
    const p = s(h);
    return o.arrayToHex(s(p.concat(o.hexToArray(e))))
}
function h(e) {
    const t = l.multiply(new i(e,16));
    return "04" + o.leftPad(t.getX().toBigInteger().toString(16), 64) + o.leftPad(t.getY().toBigInteger().toString(16), 64)
}
function f() {
    const e = o.generateKeyPairHex()
        , t = c.decodePointHex(e.publicKey);
    return e.k = new i(e.privateKey,16),
    e.x1 = t.getX().toBigInteger(),
    e
}
module.exports = {
    generateKeyPairHex: o.generateKeyPairHex,
    compressPublicKeyHex: o.compressPublicKeyHex,
    comparePublicKeyHex: o.comparePublicKeyHex,
    doEncrypt: function(e, t, n=1) {
        // console.log(e)
        // return false
        e = o.hexToArray(o.utf8ToHex(e)),


        t = o.getGlobalCurve().decodePointHex(t);
        const r = o.generateKeyPairHex()
            , a = new i(r.privateKey,16);
        let l = r.publicKey;
        l.length > 128 && (l = l.substr(l.length - 128));

        const c = t.multiply(a)
            , u = o.hexToArray(o.leftPad(c.getX().toBigInteger().toRadix(16), 64))
            , d = o.hexToArray(o.leftPad(c.getY().toBigInteger().toRadix(16), 64))
            , h = o.arrayToHex(s([].concat(u, e, d)));

        // console.log(s([].concat(u, e, d)))
        // return false
        let f = 1
            , p = 0
            , m = [];
        const g = [].concat(u, d)
            , v = () => {
            m = s([...g, f >> 24 & 255, f >> 16 & 255, f >> 8 & 255, 255 & f]),
            f++,
            p = 0
        }
        ;
        v();
        for (let i = 0, o = e.length; i < o; i++)
            p === m.length && v(),
            e[i] ^= 255 & m[p++];
        const y = o.arrayToHex(e);
        return 0 === n ? l + y + h : l + h + y
    },
    doDecrypt: function(e, t, n=1, {output: r="string"}={}) {
        t = new i(t,16);
        let a = e.substr(128, 64)
            , l = e.substr(192);
        0 === n && (a = e.substr(e.length - 64),
        l = e.substr(128, e.length - 128 - 64));
        const c = o.hexToArray(l)
            , u = o.getGlobalCurve().decodePointHex("04" + e.substr(0, 128)).multiply(t)
            , d = o.hexToArray(o.leftPad(u.getX().toBigInteger().toRadix(16), 64))
            , h = o.hexToArray(o.leftPad(u.getY().toBigInteger().toRadix(16), 64));
        let f = 1
            , p = 0
            , m = [];
        const g = [].concat(d, h)
            , v = () => {
            m = s([...g, f >> 24 & 255, f >> 16 & 255, f >> 8 & 255, 255 & f]),
            f++,
            p = 0
        }
        ;
        v();
        for (let i = 0, o = c.length; i < o; i++)
            p === m.length && v(),
            c[i] ^= 255 & m[p++];
        return o.arrayToHex(s([].concat(d, c, h))) === a.toLowerCase() ? "array" === r ? c : o.arrayToUtf8(c) : "array" === r ? [] : ""
    },
    doSignature: function(e, t, {pointPool: n, der: a, hash: s, publicKey: l, userId: c}={}) {
        let p = "string" == typeof e ? o.utf8ToHex(e) : o.arrayToHex(e);
        s && (p = d(p, l = l || h(t), c));
        const m = new i(t,16)
            , g = new i(p,16);
        let v = null
            , y = null
            , b = null;
        do {
            do {
                let e;
                e = n && n.length ? n.pop() : f(),
                v = e.k,
                y = g.add(e.x1).mod(u)
            } while (y.equals(i.ZERO) || y.add(v).equals(u));
            b = m.add(i.ONE).modInverse(u).multiply(v.subtract(y.multiply(m))).mod(u)
        } while (b.equals(i.ZERO));
        return a ? r(y, b) : o.leftPad(y.toString(16), 64) + o.leftPad(b.toString(16), 64)
    },
    doVerifySignature: function(e, t, n, {der: r, hash: s, userId: h}={}) {
        let f, p, m = "string" == typeof e ? o.utf8ToHex(e) : o.arrayToHex(e);
        if (s && (m = d(m, n, h)),
        r) {
            const e = a(t);
            f = e.r,
            p = e.s
        } else
            f = new i(t.substring(0, 64),16),
            p = new i(t.substring(64),16);
        const g = c.decodePointHex(n)
            , v = new i(m,16)
            , y = f.add(p).mod(u);
        if (y.equals(i.ZERO))
            return !1;
        const b = l.multiply(p).add(g.multiply(y))
            , _ = v.add(b.getX().toBigInteger()).mod(u);
        return f.equals(_)
    },
    getPublicKeyFromPrivateKey: h,
    getPoint: f,
    verifyPublicKey: o.verifyPublicKey
}

