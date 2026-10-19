const {BigInteger: i} = require('./f33e')
    , r = new i("2")
    , a = new i("3");
class o {
    constructor(e, t) {
        this.x = t,
        this.q = e
    }
    equals(e) {
        return e === this || this.q.equals(e.q) && this.x.equals(e.x)
    }
    toBigInteger() {
        return this.x
    }
    negate() {
        return new o(this.q,this.x.negate().mod(this.q))
    }
    add(e) {
        return new o(this.q,this.x.add(e.toBigInteger()).mod(this.q))
    }
    subtract(e) {
        return new o(this.q,this.x.subtract(e.toBigInteger()).mod(this.q))
    }
    multiply(e) {
        return new o(this.q,this.x.multiply(e.toBigInteger()).mod(this.q))
    }
    divide(e) {
        return new o(this.q,this.x.multiply(e.toBigInteger().modInverse(this.q)).mod(this.q))
    }
    square() {
        return new o(this.q,this.x.square().mod(this.q))
    }
}
class s {
    constructor(e, t, n, r) {
        this.curve = e,
        this.x = t,
        this.y = n,
        this.z = null == r ? i.ONE : r,
        this.zinv = null
    }
    getX() {
        return null === this.zinv && (this.zinv = this.z.modInverse(this.curve.q)),
        this.curve.fromBigInteger(this.x.toBigInteger().multiply(this.zinv).mod(this.curve.q))
    }
    getY() {
        return null === this.zinv && (this.zinv = this.z.modInverse(this.curve.q)),
        this.curve.fromBigInteger(this.y.toBigInteger().multiply(this.zinv).mod(this.curve.q))
    }
    equals(e) {
        return e === this || (this.isInfinity() ? e.isInfinity() : e.isInfinity() ? this.isInfinity() : !!e.y.toBigInteger().multiply(this.z).subtract(this.y.toBigInteger().multiply(e.z)).mod(this.curve.q).equals(i.ZERO) && e.x.toBigInteger().multiply(this.z).subtract(this.x.toBigInteger().multiply(e.z)).mod(this.curve.q).equals(i.ZERO))
    }
    isInfinity() {
        return null === this.x && null === this.y || this.z.equals(i.ZERO) && !this.y.toBigInteger().equals(i.ZERO)
    }
    negate() {
        return new s(this.curve,this.x,this.y.negate(),this.z)
    }
    add(e) {
        if (this.isInfinity())
            return e;
        if (e.isInfinity())
            return this;
        const t = this.x.toBigInteger()
            , n = this.y.toBigInteger()
            , r = this.z
            , a = e.x.toBigInteger()
            , o = e.y.toBigInteger()
            , l = e.z
            , c = this.curve.q
            , u = t.multiply(l).mod(c)
            , d = a.multiply(r).mod(c)
            , h = u.subtract(d)
            , f = n.multiply(l).mod(c)
            , p = o.multiply(r).mod(c)
            , m = f.subtract(p);
        if (i.ZERO.equals(h))
            return i.ZERO.equals(m) ? this.twice() : this.curve.infinity;
        const g = u.add(d)
            , v = r.multiply(l).mod(c)
            , y = h.square().mod(c)
            , b = h.multiply(y).mod(c)
            , _ = v.multiply(m.square()).subtract(g.multiply(y)).mod(c)
            , w = h.multiply(_).mod(c)
            , x = m.multiply(y.multiply(u).subtract(_)).subtract(f.multiply(b)).mod(c)
            , k = b.multiply(v).mod(c);
        return new s(this.curve,this.curve.fromBigInteger(w),this.curve.fromBigInteger(x),k)
    }
    twice() {
        if (this.isInfinity())
            return this;
        if (!this.y.toBigInteger().signum())
            return this.curve.infinity;
        const e = this.x.toBigInteger()
            , t = this.y.toBigInteger()
            , n = this.z
            , i = this.curve.q
            , r = this.curve.a.toBigInteger()
            , o = e.square().multiply(a).add(r.multiply(n.square())).mod(i)
            , l = t.shiftLeft(1).multiply(n).mod(i)
            , c = t.square().mod(i)
            , u = c.multiply(e).multiply(n).mod(i)
            , d = l.square().mod(i)
            , h = o.square().subtract(u.shiftLeft(3)).mod(i)
            , f = l.multiply(h).mod(i)
            , p = o.multiply(u.shiftLeft(2).subtract(h)).subtract(d.shiftLeft(1).multiply(c)).mod(i)
            , m = l.multiply(d).mod(i);
        return new s(this.curve,this.curve.fromBigInteger(f),this.curve.fromBigInteger(p),m)
    }
    multiply(e) {
        if (this.isInfinity())
            return this;
        if (!e.signum())
            return this.curve.infinity;
        const t = e.multiply(a)
            , n = this.negate();
        let i = this;
        for (let r = t.bitLength() - 2; r > 0; r--) {
            i = i.twice();
            const a = t.testBit(r);
            a !== e.testBit(r) && (i = i.add(a ? this : n))
        }
        return i
    }
}
module.exports = {
    ECPointFp: s,
    ECCurveFp: class {
        constructor(e, t, n) {
            this.q = e,
            this.a = this.fromBigInteger(t),
            this.b = this.fromBigInteger(n),
            this.infinity = new s(this,null,null)
        }
        equals(e) {
            return e === this || this.q.equals(e.q) && this.a.equals(e.a) && this.b.equals(e.b)
        }
        fromBigInteger(e) {
            return new o(this.q,e)
        }
        decodePointHex(e) {
            switch (parseInt(e.substr(0, 2), 16)) {
            case 0:
                return this.infinity;
            case 2:
            case 3:
                const t = this.fromBigInteger(new i(e.substr(2),16));
                let n = this.fromBigInteger(t.multiply(t.square()).add(t.multiply(this.a)).add(this.b).toBigInteger().modPow(this.q.divide(new i("4")).add(i.ONE), this.q));
                return n.toBigInteger().mod(r).equals(new i(e.substr(0, 2),16).subtract(r)) || (n = n.negate()),
                new s(this,t,n);
            case 4:
            case 6:
            case 7:
                const a = (e.length - 2) / 2
                    , o = e.substr(2, a)
                    , l = e.substr(a + 2, a);
                return new s(this,this.fromBigInteger(new i(o,16)),this.fromBigInteger(new i(l,16)));
            default:
                return null
            }
        }
    }
}