// ecModule.js
const { BigInteger, SecureRandom } = require('./f33e'); // 替换为实际的库
const { ECCurveFp } = require('./4701'); // 替换为实际的库
const {curve: s, G: l, n: c} = u();
const o = new SecureRandom
function u() {
    const e = new BigInteger("FFFFFFFEFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF00000000FFFFFFFFFFFFFFFF",16)
      , t = new BigInteger("FFFFFFFEFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF00000000FFFFFFFFFFFFFFFC",16)
      , n = new BigInteger("28E9FA9E9D9F5E344D5A9E4BCF6509A7F39789F515AB8F92DDBCBD414D940E93",16)
      , r = new ECCurveFp(e,t,n)
      , o = r.decodePointHex("0432C4AE2C1F1981195F9904466A39C9948FE30BBFF2660BE1715A4589334C74C7BC3736A2F4F6779C59BDCEE36B692153D0A9877CC62A474002DF32E52139F0A0");
    return {
        curve: r,
        G: o,
        n: new BigInteger("FFFFFFFEFFFFFFFFFFFFFFFFFFFFFFFF7203DF6B21C6052B53BBF40939D54123",16)
    }
}
function d(e, t) {
    return e.length >= t ? e : new Array(t - e.length + 1).join("0") + e
}


module.exports = {
    getGlobalCurve: function() {
        return s
    },
    generateEcparam: u,
    generateKeyPairHex: function(e, t, n) {
        const r = (e ? new BigInteger(e,t,n) : new BigInteger(c.bitLength(),o)).mod(c.subtract(BigInteger.ONE)).add(BigInteger.ONE)
          , a = d(r.toString(16), 64)
          , s = l.multiply(r);
        return {
            privateKey: a,
            publicKey: "04" + d(s.getX().toBigInteger().toString(16), 64) + d(s.getY().toBigInteger().toString(16), 64)
        }
    },
    compressPublicKeyHex: function(e) {
        if (130 !== e.length)
            throw new Error("Invalid public key to compress");
        const t = (e.length - 2) / 2
          , n = e.substr(2, t);
        let r = "03";
        return new BigInteger(e.substr(t + 2, t),16).mod(new BigInteger("2")).equals(i.ZERO) && (r = "02"),
        r + n
    },
    utf8ToHex: function(e) {
        const t = (e = unescape(encodeURIComponent(e))).length
          , n = [];
        for (let r = 0; r < t; r++)
            n[r >>> 2] |= (255 & e.charCodeAt(r)) << 24 - r % 4 * 8;
        const i = [];
        for (let r = 0; r < t; r++) {
            const e = n[r >>> 2] >>> 24 - r % 4 * 8 & 255;
            i.push((e >>> 4).toString(16)),
            i.push((15 & e).toString(16))
        }
        return i.join("")
    },
    leftPad: d,
    arrayToHex: function(e) {
        return e.map(e => 1 === (e = e.toString(16)).length ? "0" + e : e).join("")
    },
    arrayToUtf8: function(e) {
        const t = [];
        let n = 0;
        for (let i = 0; i < 2 * e.length; i += 2)
            t[i >>> 3] |= parseInt(e[n], 10) << 24 - i % 8 * 4,
            n++;
        try {
            const n = [];
            for (let i = 0; i < e.length; i++) {
                const e = t[i >>> 2] >>> 24 - i % 4 * 8 & 255;
                n.push(String.fromCharCode(e))
            }
            return decodeURIComponent(escape(n.join("")))
        } catch (e) {
            throw new Error("Malformed UTF-8 data")
        }
    },
    hexToArray: function(e) {
        const t = [];
        let n = e.length;
        n % 2 != 0 && (e = d(e, n + 1)),
        n = e.length;
        for (let i = 0; i < n; i += 2)
            t.push(parseInt(e.substr(i, 2), 16));
        return t
    },
    verifyPublicKey: function(e) {
        const t = s.decodePointHex(e);
        if (!t)
            return !1;
        const n = t.getX();
        return t.getY().square().equals(n.multiply(n.square()).add(n.multiply(s.a)).add(s.b))
    },
    comparePublicKeyHex: function(e, t) {
        const n = s.decodePointHex(e);
        if (!n)
            return !1;
        const i = s.decodePointHex(t);
        return !!i && n.equals(i)
    }

};
