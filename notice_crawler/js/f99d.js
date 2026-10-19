const {BigInteger: i} = require("./f33e");
class r {
    constructor() {
        this.tlv = null,
        this.t = "00",
        this.l = "00",
        this.v = ""
    }
    getEncodedHex() {
        return this.tlv || (this.v = this.getValue(),
        this.l = this.getLength(),
        this.tlv = this.t + this.l + this.v),
        this.tlv
    }
    getLength() {
        const e = this.v.length / 2;
        let t = e.toString(16);
        return t.length % 2 == 1 && (t = "0" + t),
        e < 128 ? t : (128 + t.length / 2).toString(16) + t
    }
    getValue() {
        return ""
    }
}
class a extends r {
    constructor(e) {
        super(),
        this.t = "02",
        e && (this.v = function(e) {
            let t = e.toString(16);
            if ("-" !== t[0])
                t.length % 2 == 1 ? t = "0" + t : t.match(/^[0-7]/) || (t = "00" + t);
            else {
                t = t.substr(1);
                let n = t.length;
                n % 2 == 1 ? n += 1 : t.match(/^[0-7]/) || (n += 2);
                let r = "";
                for (let e = 0; e < n; e++)
                    r += "f";
                r = new i(r,16),
                t = r.xor(e).add(i.ONE),
                t = t.toString(16).replace(/^-/, "")
            }
            return t
        }(e))
    }
    getValue() {
        return this.v
    }
}
class o extends r {
    constructor(e) {
        super(),
        this.t = "30",
        this.asn1Array = e
    }
    getValue() {
        return this.v = this.asn1Array.map(e => e.getEncodedHex()).join(""),
        this.v
    }
}
function s(e, t) {
    return +e[t + 2] < 8 ? 1 : 128 & +e.substr(t + 2, 2)
}
function l(e, t) {
    const n = s(e, t)
        , r = e.substr(t + 2, 2 * n);
    return r ? (+r[0] < 8 ? new i(r,16) : new i(r.substr(2),16)).intValue() : -1
}
function c(e, t) {
    return t + 2 * (s(e, t) + 1)
}
module.exports = {
    encodeDer(e, t) {
        const n = new a(e)
            , i = new a(t);
        return new o([n, i]).getEncodedHex()
    },
    decodeDer(e) {
        const t = c(e, 0)
            , n = c(e, t)
            , r = l(e, t)
            , a = e.substr(n, 2 * r)
            , o = n + a.length
            , s = c(e, o)
            , u = l(e, o)
            , d = e.substr(s, 2 * u);
        return {
            r: new i(a,16),
            s: new i(d,16)
        }
    }
}