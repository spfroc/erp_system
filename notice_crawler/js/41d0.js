const n = new Uint32Array(68)
    , i = new Uint32Array(64);
function r(e, t) {
    const n = 31 & t;
    return e << n | e >>> 32 - n
}
function a(e, t) {
    const n = [];
    for (let i = e.length - 1; i >= 0; i--)
        n[i] = 255 & (e[i] ^ t[i]);
    return n
}
function o(e) {
    return e ^ r(e, 9) ^ r(e, 17)
}
function s(e) {
    let t = 8 * e.length
        , a = t % 512;
    a = a >= 448 ? 512 - a % 448 - 1 : 448 - a - 1;
    const s = new Array((a - 7) / 8)
        , l = new Array(8);
    for (let n = 0, i = s.length; n < i; n++)
        s[n] = 0;
    for (let n = 0, i = l.length; n < i; n++)
        l[n] = 0;
    t = t.toString(2);
    for (let n = 7; n >= 0; n--)
        if (t.length > 8) {
            const e = t.length - 8;
            l[n] = parseInt(t.substr(e), 2),
            t = t.substr(0, e)
        } else
            t.length > 0 && (l[n] = parseInt(t, 2),
            t = "");
    const c = new Uint8Array([...e, 128, ...s, ...l])
        , u = new DataView(c.buffer,0)
        , d = c.length / 64
        , h = new Uint32Array([1937774191, 1226093241, 388252375, 3666478592, 2842636476, 372324522, 3817729613, 2969243214]);
    for (let m = 0; m < d; m++) {
        n.fill(0),
        i.fill(0);
        const e = 16 * m;
        for (let i = 0; i < 16; i++)
            n[i] = u.getUint32(4 * (e + i), !1);
        for (let i = 16; i < 68; i++)
            n[i] = (f = n[i - 16] ^ n[i - 9] ^ r(n[i - 3], 15)) ^ r(f, 15) ^ r(f, 23) ^ r(n[i - 13], 7) ^ n[i - 6];
        for (let r = 0; r < 64; r++)
            i[r] = n[r] ^ n[r + 4];
        const t = 2043430169
            , a = 2055708042;
        let s, l, c, d, p, g = h[0], v = h[1], y = h[2], b = h[3], _ = h[4], w = h[5], x = h[6], k = h[7];
        for (let u = 0; u < 64; u++)
            p = u >= 0 && u <= 15 ? t : a,
            s = r(r(g, 12) + _ + r(p, u), 7),
            l = s ^ r(g, 12),
            c = (u >= 0 && u <= 15 ? g ^ v ^ y : g & v | g & y | v & y) + b + l + i[u],
            d = (u >= 0 && u <= 15 ? _ ^ w ^ x : _ & w | ~_ & x) + k + s + n[u],
            b = y,
            y = r(v, 9),
            v = g,
            g = c,
            k = x,
            x = r(w, 19),
            w = _,
            _ = o(d);
        h[0] ^= g,
        h[1] ^= v,
        h[2] ^= y,
        h[3] ^= b,
        h[4] ^= _,
        h[5] ^= w,
        h[6] ^= x,
        h[7] ^= k
    }
    var f;
    const p = [];
    for (let n = 0, i = h.length; n < i; n++) {
        const e = h[n];
        p.push((4278190080 & e) >>> 24, (16711680 & e) >>> 16, (65280 & e) >>> 8, 255 & e)
    }

    return p
}
const l = new Uint8Array(64)
    , c = new Uint8Array(64);
for (let u = 0; u < 64; u++)
    l[u] = 54,
    c[u] = 92;


module.exports = {
    sm3: s,
    // hmac: hmac
};
