(function() {
    var t = 28;
    function n(e, t, n) {
        null != e && ("number" == typeof e ? this.fromNumber(e, t, n) : null == t && "string" != typeof e ? this.fromString(e, 256) : this.fromString(e, t))
    }

    function i() {
        return new n(null)
    }

    n.prototype.am = function(e, t, n, i, r, a) {
        for (var o = 16383 & t, s = t >> 14; --a >= 0; ) {
            var l = 16383 & this[e]
              , c = this[e++] >> 14
              , u = s * l + c * o;
            r = ((l = o * l + ((16383 & u) << 14) + n[i] + r) >> 28) + (u >> 14) + s * c,
            n[i++] = 268435455 & l
        }
        return r
    }
    ,
    n.prototype.DB = t,
    n.prototype.DM = (1 << t) - 1,
    n.prototype.DV = 1 << t,
    n.prototype.FV = Math.pow(2, 52),
    n.prototype.F1 = 52 - t,
    n.prototype.F2 = 2 * t - 52;
    var a, o, s = "0123456789abcdefghijklmnopqrstuvwxyz", l = new Array;
    for (a = "0".charCodeAt(0),
    o = 0; o <= 9; ++o)
        l[a++] = o;
    for (a = "a".charCodeAt(0),
    o = 10; o < 36; ++o)
        l[a++] = o;
    for (a = "A".charCodeAt(0),
    o = 10; o < 36; ++o)
        l[a++] = o;
    function c(e) {
        return s.charAt(e)
    }
    function u(e, t) {
        var n = l[e.charCodeAt(t)];
        return null == n ? -1 : n
    }
    function d(e) {
        var t = i();
        return t.fromInt(e),
        t
    }
    function h(e) {
        var t, n = 1;
        return 0 != (t = e >>> 16) && (e = t,
        n += 16),
        0 != (t = e >> 8) && (e = t,
        n += 8),
        0 != (t = e >> 4) && (e = t,
        n += 4),
        0 != (t = e >> 2) && (e = t,
        n += 2),
        0 != (t = e >> 1) && (e = t,
        n += 1),
        n
    }
    function f(e) {
        this.m = e
    }
    function p(e) {
        this.m = e,
        this.mp = e.invDigit(),
        this.mpl = 32767 & this.mp,
        this.mph = this.mp >> 15,
        this.um = (1 << e.DB - 15) - 1,
        this.mt2 = 2 * e.t
    }
    function m(e, t) {
        return e & t
    }
    function g(e, t) {
        return e | t
    }
    function v(e, t) {
        return e ^ t
    }
    function y(e, t) {
        return e & ~t
    }
    function b(e) {
        if (0 == e)
            return -1;
        var t = 0;
        return 65535 & e || (e >>= 16,
        t += 16),
        255 & e || (e >>= 8,
        t += 8),
        15 & e || (e >>= 4,
        t += 4),
        3 & e || (e >>= 2,
        t += 2),
        1 & e || ++t,
        t
    }
    function _(e) {
        for (var t = 0; 0 != e; )
            e &= e - 1,
            ++t;
        return t
    }
    function w() {}
    function x(e) {
        return e
    }
    function k(e) {
        this.r2 = i(),
        this.q3 = i(),
        n.ONE.dlShiftTo(2 * e.t, this.r2),
        this.mu = this.r2.divide(e),
        this.m = e
    }
    f.prototype.convert = function(e) {
        return e.s < 0 || e.compareTo(this.m) >= 0 ? e.mod(this.m) : e
    }
    ,
    f.prototype.revert = function(e) {
        return e
    }
    ,
    f.prototype.reduce = function(e) {
        e.divRemTo(this.m, null, e)
    }
    ,
    f.prototype.mulTo = function(e, t, n) {
        e.multiplyTo(t, n),
        this.reduce(n)
    }
    ,
    f.prototype.sqrTo = function(e, t) {
        e.squareTo(t),
        this.reduce(t)
    }
    ,
    p.prototype.convert = function(e) {
        var t = i();
        return e.abs().dlShiftTo(this.m.t, t),
        t.divRemTo(this.m, null, t),
        e.s < 0 && t.compareTo(n.ZERO) > 0 && this.m.subTo(t, t),
        t
    }
    ,
    p.prototype.revert = function(e) {
        var t = i();
        return e.copyTo(t),
        this.reduce(t),
        t
    }
    ,
    // p.prototype.reduce = function(e) {
    //     for (; e.t <= this.mt2; )
    //         e[e.t++] = 0;
    //     for (var t = 0; t < this.m.t; ++t) {
    //         var n = 32767 & e[t]
    //           , i = n * this.mpl + ((n * this.mph + (e[t] >> 15) * this.mpl & this.um) << 15) & e.DM;
    //         for (e[n = t + this.m.t] += this.m.am(0, i, e, t, 0, this.m.t); e[n] >= e.DV; )
    //             e[n] -= e.DV,
    //             e[++n]++
    //     }
    //     e.clamp(),
    //     e.drShiftTo(this.m.t, e),
    //     e.compareTo(this.m) >= 0 && e.subTo(this.m, e)
    // }
    // ,
    // p.prototype.mulTo = function(e, t, n) {
    //     e.multiplyTo(t, n),
    //     this.reduce(n)
    // }
    // ,
    // p.prototype.sqrTo = function(e, t) {
    //     e.squareTo(t),
    //     this.reduce(t)
    // }
    // ,
    n.prototype.copyTo = function(e) {
        for (var t = this.t - 1; t >= 0; --t)
            e[t] = this[t];
        e.t = this.t,
        e.s = this.s
    }
    ,
    n.prototype.fromInt = function(e) {
        this.t = 1,
        this.s = e < 0 ? -1 : 0,
        e > 0 ? this[0] = e : e < -1 ? this[0] = e + this.DV : this.t = 0
    }
    ,
    n.prototype.fromString = function(e, t) {
        var i;
        if (16 == t)
            i = 4;
        else if (8 == t)
            i = 3;
        else if (256 == t)
            i = 8;
        else if (2 == t)
            i = 1;
        else if (32 == t)
            i = 5;
        else {
            if (4 != t)
                return void this.fromRadix(e, t);
            i = 2
        }
        this.t = 0,
        this.s = 0;
        for (var r = e.length, a = !1, o = 0; --r >= 0; ) {
            var s = 8 == i ? 255 & e[r] : u(e, r);
            s < 0 ? "-" == e.charAt(r) && (a = !0) : (a = !1,
            0 == o ? this[this.t++] = s : o + i > this.DB ? (this[this.t - 1] |= (s & (1 << this.DB - o) - 1) << o,
            this[this.t++] = s >> this.DB - o) : this[this.t - 1] |= s << o,
            (o += i) >= this.DB && (o -= this.DB))
        }
        8 == i && 128 & e[0] && (this.s = -1,
        o > 0 && (this[this.t - 1] |= (1 << this.DB - o) - 1 << o)),
        this.clamp(),
        a && n.ZERO.subTo(this, this)
    }
    ,
    n.prototype.clamp = function() {
        for (var e = this.s & this.DM; this.t > 0 && this[this.t - 1] == e; )
            --this.t
    }
    ,
    n.prototype.dlShiftTo = function(e, t) {
        var n;
        for (n = this.t - 1; n >= 0; --n)
            t[n + e] = this[n];
        for (n = e - 1; n >= 0; --n)
            t[n] = 0;
        t.t = this.t + e,
        t.s = this.s
    }
    ,
    n.prototype.drShiftTo = function(e, t) {
        for (var n = e; n < this.t; ++n)
            t[n - e] = this[n];
        t.t = Math.max(this.t - e, 0),
        t.s = this.s
    }
    ,
    n.prototype.lShiftTo = function(e, t) {
        var n, i = e % this.DB, r = this.DB - i, a = (1 << r) - 1, o = Math.floor(e / this.DB), s = this.s << i & this.DM;
        for (n = this.t - 1; n >= 0; --n)
            t[n + o + 1] = this[n] >> r | s,
            s = (this[n] & a) << i;
        for (n = o - 1; n >= 0; --n)
            t[n] = 0;
        t[o] = s,
        t.t = this.t + o + 1,
        t.s = this.s,
        t.clamp()
    }
    ,
    n.prototype.rShiftTo = function(e, t) {
        t.s = this.s;
        var n = Math.floor(e / this.DB);
        if (n >= this.t)
            t.t = 0;
        else {
            var i = e % this.DB
              , r = this.DB - i
              , a = (1 << i) - 1;
            t[0] = this[n] >> i;
            for (var o = n + 1; o < this.t; ++o)
                t[o - n - 1] |= (this[o] & a) << r,
                t[o - n] = this[o] >> i;
            i > 0 && (t[this.t - n - 1] |= (this.s & a) << r),
            t.t = this.t - n,
            t.clamp()
        }
    }
    ,
    n.prototype.subTo = function(e, t) {
        for (var n = 0, i = 0, r = Math.min(e.t, this.t); n < r; )
            i += this[n] - e[n],
            t[n++] = i & this.DM,
            i >>= this.DB;
        if (e.t < this.t) {
            for (i -= e.s; n < this.t; )
                i += this[n],
                t[n++] = i & this.DM,
                i >>= this.DB;
            i += this.s
        } else {
            for (i += this.s; n < e.t; )
                i -= e[n],
                t[n++] = i & this.DM,
                i >>= this.DB;
            i -= e.s
        }
        t.s = i < 0 ? -1 : 0,
        i < -1 ? t[n++] = this.DV + i : i > 0 && (t[n++] = i),
        t.t = n,
        t.clamp()
    }
    ,
    n.prototype.multiplyTo = function(e, t) {
        var i = this.abs()
          , r = e.abs()
          , a = i.t;
        for (t.t = a + r.t; --a >= 0; )
            t[a] = 0;
        for (a = 0; a < r.t; ++a)
            t[a + i.t] = i.am(0, r[a], t, a, 0, i.t);
        t.s = 0,
        t.clamp(),
        this.s != e.s && n.ZERO.subTo(t, t)
    }
    ,
    n.prototype.squareTo = function(e) {
        for (var t = this.abs(), n = e.t = 2 * t.t; --n >= 0; )
            e[n] = 0;
        for (n = 0; n < t.t - 1; ++n) {
            var i = t.am(n, t[n], e, 2 * n, 0, 1);
            (e[n + t.t] += t.am(n + 1, 2 * t[n], e, 2 * n + 1, i, t.t - n - 1)) >= t.DV && (e[n + t.t] -= t.DV,
            e[n + t.t + 1] = 1)
        }
        e.t > 0 && (e[e.t - 1] += t.am(n, t[n], e, 2 * n, 0, 1)),
        e.s = 0,
        e.clamp()
    }
    ,
    n.prototype.divRemTo = function(e, t, r) {
        var a = e.abs();
        if (!(a.t <= 0)) {
            var o = this.abs();
            if (o.t < a.t)
                return null != t && t.fromInt(0),
                void (null != r && this.copyTo(r));
            null == r && (r = i());
            var s = i()
              , l = this.s
              , c = e.s
              , u = this.DB - h(a[a.t - 1]);
            u > 0 ? (a.lShiftTo(u, s),
            o.lShiftTo(u, r)) : (a.copyTo(s),
            o.copyTo(r));
            var d = s.t
              , f = s[d - 1];
            if (0 != f) {
                var p = f * (1 << this.F1) + (d > 1 ? s[d - 2] >> this.F2 : 0)
                  , m = this.FV / p
                  , g = (1 << this.F1) / p
                  , v = 1 << this.F2
                  , y = r.t
                  , b = y - d
                  , _ = null == t ? i() : t;
                for (s.dlShiftTo(b, _),
                r.compareTo(_) >= 0 && (r[r.t++] = 1,
                r.subTo(_, r)),
                n.ONE.dlShiftTo(d, _),
                _.subTo(s, s); s.t < d; )
                    s[s.t++] = 0;
                for (; --b >= 0; ) {
                    var w = r[--y] == f ? this.DM : Math.floor(r[y] * m + (r[y - 1] + v) * g);
                    if ((r[y] += s.am(0, w, r, b, 0, d)) < w)
                        for (s.dlShiftTo(b, _),
                        r.subTo(_, r); r[y] < --w; )
                            r.subTo(_, r)
                }
                null != t && (r.drShiftTo(d, t),
                l != c && n.ZERO.subTo(t, t)),
                r.t = d,
                r.clamp(),
                u > 0 && r.rShiftTo(u, r),
                l < 0 && n.ZERO.subTo(r, r)
            }
        }
    }
    ,
    n.prototype.invDigit = function() {
        if (this.t < 1)
            return 0;
        var e = this[0];
        if (!(1 & e))
            return 0;
        var t = 3 & e;
        return (t = (t = (t = (t = t * (2 - (15 & e) * t) & 15) * (2 - (255 & e) * t) & 255) * (2 - ((65535 & e) * t & 65535)) & 65535) * (2 - e * t % this.DV) % this.DV) > 0 ? this.DV - t : -t
    }
    ,
    n.prototype.isEven = function() {
        return 0 == (this.t > 0 ? 1 & this[0] : this.s)
    }
    ,
    n.prototype.exp = function(e, t) {
        if (e > 4294967295 || e < 1)
            return n.ONE;
        var r = i()
          , a = i()
          , o = t.convert(this)
          , s = h(e) - 1;
        for (o.copyTo(r); --s >= 0; )
            if (t.sqrTo(r, a),
            (e & 1 << s) > 0)
                t.mulTo(a, o, r);
            else {
                var l = r;
                r = a,
                a = l
            }
        return t.revert(r)
    }
    ,
    n.prototype.toString = function(e) {
        if (this.s < 0)
            return "-" + this.negate().toString(e);
        var t;
        if (16 == e)
            t = 4;
        else if (8 == e)
            t = 3;
        else if (2 == e)
            t = 1;
        else if (32 == e)
            t = 5;
        else {
            if (4 != e)
                return this.toRadix(e);
            t = 2
        }
        var n, i = (1 << t) - 1, r = !1, a = "", o = this.t, s = this.DB - o * this.DB % t;
        if (o-- > 0)
            for (s < this.DB && (n = this[o] >> s) > 0 && (r = !0,
            a = c(n)); o >= 0; )
                s < t ? (n = (this[o] & (1 << s) - 1) << t - s,
                n |= this[--o] >> (s += this.DB - t)) : (n = this[o] >> (s -= t) & i,
                s <= 0 && (s += this.DB,
                --o)),
                n > 0 && (r = !0),
                r && (a += c(n));
        return r ? a : "0"
    }
    ,
    n.prototype.negate = function() {
        var e = i();
        return n.ZERO.subTo(this, e),
        e
    }
    ,
    n.prototype.abs = function() {
        return this.s < 0 ? this.negate() : this
    }
    ,
    n.prototype.compareTo = function(e) {
        var t = this.s - e.s;
        if (0 != t)
            return t;
        var n = this.t;
        if (0 != (t = n - e.t))
            return this.s < 0 ? -t : t;
        for (; --n >= 0; )
            if (0 != (t = this[n] - e[n]))
                return t;
        return 0
    }
    ,
    n.prototype.bitLength = function() {
        return this.t <= 0 ? 0 : this.DB * (this.t - 1) + h(this[this.t - 1] ^ this.s & this.DM)
    }
    ,
    n.prototype.mod = function(e) {
        var t = i();
        return this.abs().divRemTo(e, null, t),
        this.s < 0 && t.compareTo(n.ZERO) > 0 && e.subTo(t, t),
        t
    }
    ,
    n.prototype.modPowInt = function(e, t) {
        var n;
        return n = e < 256 || t.isEven() ? new f(t) : new p(t),
        this.exp(e, n)
    }
    ,
    n.ZERO = d(0),
    n.ONE = d(1),
    w.prototype.convert = x,
    w.prototype.revert = x,
    w.prototype.mulTo = function(e, t, n) {
        e.multiplyTo(t, n)
    }
    ,
    w.prototype.sqrTo = function(e, t) {
        e.squareTo(t)
    }
    ,
    k.prototype.convert = function(e) {
        if (e.s < 0 || e.t > 2 * this.m.t)
            return e.mod(this.m);
        if (e.compareTo(this.m) < 0)
            return e;
        var t = i();
        return e.copyTo(t),
        this.reduce(t),
        t
    }
    ,
    // k.prototype.revert = function(e) {
    //     return e
    // }
    // ,
    // k.prototype.reduce = function(e) {
    //     for (e.drShiftTo(this.m.t - 1, this.r2),
    //     e.t > this.m.t + 1 && (e.t = this.m.t + 1,
    //     e.clamp()),
    //     this.mu.multiplyUpperTo(this.r2, this.m.t + 1, this.q3),
    //     this.m.multiplyLowerTo(this.q3, this.m.t + 1, this.r2); e.compareTo(this.r2) < 0; )
    //         e.dAddOffset(1, this.m.t + 1);
    //     for (e.subTo(this.r2, e); e.compareTo(this.m) >= 0; )
    //         e.subTo(this.m, e)
    // }
    // ,
    // k.prototype.mulTo = function(e, t, n) {
    //     e.multiplyTo(t, n),
    //     this.reduce(n)
    // }
    // ,
    k.prototype.sqrTo = function(e, t) {
        e.squareTo(t),
        this.reduce(t)
    }
    ;
    var C, S, M, D = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59, 61, 67, 71, 73, 79, 83, 89, 97, 101, 103, 107, 109, 113, 127, 131, 137, 139, 149, 151, 157, 163, 167, 173, 179, 181, 191, 193, 197, 199, 211, 223, 227, 229, 233, 239, 241, 251, 257, 263, 269, 271, 277, 281, 283, 293, 307, 311, 313, 317, 331, 337, 347, 349, 353, 359, 367, 373, 379, 383, 389, 397, 401, 409, 419, 421, 431, 433, 439, 443, 449, 457, 461, 463, 467, 479, 487, 491, 499, 503, 509, 521, 523, 541, 547, 557, 563, 569, 571, 577, 587, 593, 599, 601, 607, 613, 617, 619, 631, 641, 643, 647, 653, 659, 661, 673, 677, 683, 691, 701, 709, 719, 727, 733, 739, 743, 751, 757, 761, 769, 773, 787, 797, 809, 811, 821, 823, 827, 829, 839, 853, 857, 859, 863, 877, 881, 883, 887, 907, 911, 919, 929, 937, 941, 947, 953, 967, 971, 977, 983, 991, 997], A = (1 << 26) / D[D.length - 1];
    function T() {
        var e;
        e = (new Date).getTime(),
        S[M++] ^= 255 & e,
        S[M++] ^= e >> 8 & 255,
        S[M++] ^= e >> 16 & 255,
        S[M++] ^= e >> 24 & 255,
        M >= Y && (M -= Y)
    }
    if (n.prototype.chunkSize = function(e) {
        return Math.floor(Math.LN2 * this.DB / Math.log(e))
    }
    ,
    n.prototype.toRadix = function(e) {
        if (null == e && (e = 10),
        0 == this.signum() || e < 2 || e > 36)
            return "0";
        var t = this.chunkSize(e)
          , n = Math.pow(e, t)
          , r = d(n)
          , a = i()
          , o = i()
          , s = "";
        for (this.divRemTo(r, a, o); a.signum() > 0; )
            s = (n + o.intValue()).toString(e).substr(1) + s,
            a.divRemTo(r, a, o);
        return o.intValue().toString(e) + s
    }
    ,
    n.prototype.fromRadix = function(e, t) {
        this.fromInt(0),
        null == t && (t = 10);
        for (var i = this.chunkSize(t), r = Math.pow(t, i), a = !1, o = 0, s = 0, l = 0; l < e.length; ++l) {
            var c = u(e, l);
            c < 0 ? "-" == e.charAt(l) && 0 == this.signum() && (a = !0) : (s = t * s + c,
            ++o >= i && (this.dMultiply(r),
            this.dAddOffset(s, 0),
            o = 0,
            s = 0))
        }
        o > 0 && (this.dMultiply(Math.pow(t, o)),
        this.dAddOffset(s, 0)),
        a && n.ZERO.subTo(this, this)
    }
    ,
    n.prototype.fromNumber = function(e, t, i) {
        if ("number" == typeof t)
            if (e < 2)
                this.fromInt(1);
            else
                for (this.fromNumber(e, i),
                this.testBit(e - 1) || this.bitwiseTo(n.ONE.shiftLeft(e - 1), g, this),
                this.isEven() && this.dAddOffset(1, 0); !this.isProbablePrime(t); )
                    this.dAddOffset(2, 0),
                    this.bitLength() > e && this.subTo(n.ONE.shiftLeft(e - 1), this);
        else {
            var r = new Array
              , a = 7 & e;
            r.length = 1 + (e >> 3),
            t.nextBytes(r),
            a > 0 ? r[0] &= (1 << a) - 1 : r[0] = 0,
            this.fromString(r, 256)
        }
    }
    ,
    n.prototype.bitwiseTo = function(e, t, n) {
        var i, r, a = Math.min(e.t, this.t);
        for (i = 0; i < a; ++i)
            n[i] = t(this[i], e[i]);
        if (e.t < this.t) {
            for (r = e.s & this.DM,
            i = a; i < this.t; ++i)
                n[i] = t(this[i], r);
            n.t = this.t
        } else {
            for (r = this.s & this.DM,
            i = a; i < e.t; ++i)
                n[i] = t(r, e[i]);
            n.t = e.t
        }
        n.s = t(this.s, e.s),
        n.clamp()
    }
    ,
    n.prototype.changeBit = function(e, t) {
        var i = n.ONE.shiftLeft(e);
        return this.bitwiseTo(i, t, i),
        i
    }
    ,
    n.prototype.addTo = function(e, t) {
        for (var n = 0, i = 0, r = Math.min(e.t, this.t); n < r; )
            i += this[n] + e[n],
            t[n++] = i & this.DM,
            i >>= this.DB;
        if (e.t < this.t) {
            for (i += e.s; n < this.t; )
                i += this[n],
                t[n++] = i & this.DM,
                i >>= this.DB;
            i += this.s
        } else {
            for (i += this.s; n < e.t; )
                i += e[n],
                t[n++] = i & this.DM,
                i >>= this.DB;
            i += e.s
        }
        t.s = i < 0 ? -1 : 0,
        i > 0 ? t[n++] = i : i < -1 && (t[n++] = this.DV + i),
        t.t = n,
        t.clamp()
    }
    ,
    n.prototype.dMultiply = function(e) {
        this[this.t] = this.am(0, e - 1, this, 0, 0, this.t),
        ++this.t,
        this.clamp()
    }
    ,
    n.prototype.dAddOffset = function(e, t) {
        if (0 != e) {
            for (; this.t <= t; )
                this[this.t++] = 0;
            for (this[t] += e; this[t] >= this.DV; )
                this[t] -= this.DV,
                ++t >= this.t && (this[this.t++] = 0),
                ++this[t]
        }
    }
    ,
    n.prototype.multiplyLowerTo = function(e, t, n) {
        var i, r = Math.min(this.t + e.t, t);
        for (n.s = 0,
        n.t = r; r > 0; )
            n[--r] = 0;
        for (i = n.t - this.t; r < i; ++r)
            n[r + this.t] = this.am(0, e[r], n, r, 0, this.t);
        for (i = Math.min(e.t, t); r < i; ++r)
            this.am(0, e[r], n, r, 0, t - r);
        n.clamp()
    }
    ,
    n.prototype.multiplyUpperTo = function(e, t, n) {
        --t;
        var i = n.t = this.t + e.t - t;
        for (n.s = 0; --i >= 0; )
            n[i] = 0;
        for (i = Math.max(t - this.t, 0); i < e.t; ++i)
            n[this.t + i - t] = this.am(t - i, e[i], n, 0, 0, this.t + i - t);
        n.clamp(),
        n.drShiftTo(1, n)
    }
    ,
    n.prototype.modInt = function(e) {
        if (e <= 0)
            return 0;
        var t = this.DV % e
          , n = this.s < 0 ? e - 1 : 0;
        if (this.t > 0)
            if (0 == t)
                n = this[0] % e;
            else
                for (var i = this.t - 1; i >= 0; --i)
                    n = (t * n + this[i]) % e;
        return n
    }
    ,
    n.prototype.millerRabin = function(e) {
        var t = this.subtract(n.ONE)
          , r = t.getLowestSetBit();
        if (r <= 0)
            return !1;
        var a = t.shiftRight(r);
        (e = e + 1 >> 1) > D.length && (e = D.length);
        for (var o = i(), s = 0; s < e; ++s) {
            o.fromInt(D[Math.floor(Math.random() * D.length)]);
            var l = o.modPow(a, this);
            if (0 != l.compareTo(n.ONE) && 0 != l.compareTo(t)) {
                for (var c = 1; c++ < r && 0 != l.compareTo(t); )
                    if (0 == (l = l.modPowInt(2, this)).compareTo(n.ONE))
                        return !1;
                if (0 != l.compareTo(t))
                    return !1
            }
        }
        return !0
    }
    ,
    n.prototype.clone = function() {
        var e = i();
        return this.copyTo(e),
        e
    }
    ,
    n.prototype.intValue = function() {
        if (this.s < 0) {
            if (1 == this.t)
                return this[0] - this.DV;
            if (0 == this.t)
                return -1
        } else {
            if (1 == this.t)
                return this[0];
            if (0 == this.t)
                return 0
        }
        return (this[1] & (1 << 32 - this.DB) - 1) << this.DB | this[0]
    }
    ,
    n.prototype.byteValue = function() {
        return 0 == this.t ? this.s : this[0] << 24 >> 24
    }
    ,
    n.prototype.shortValue = function() {
        return 0 == this.t ? this.s : this[0] << 16 >> 16
    }
    ,
    n.prototype.signum = function() {
        return this.s < 0 ? -1 : this.t <= 0 || 1 == this.t && this[0] <= 0 ? 0 : 1
    }
    ,
    n.prototype.toByteArray = function() {
        var e = this.t
          , t = new Array;
        t[0] = this.s;
        var n, i = this.DB - e * this.DB % 8, r = 0;
        if (e-- > 0)
            for (i < this.DB && (n = this[e] >> i) != (this.s & this.DM) >> i && (t[r++] = n | this.s << this.DB - i); e >= 0; )
                i < 8 ? (n = (this[e] & (1 << i) - 1) << 8 - i,
                n |= this[--e] >> (i += this.DB - 8)) : (n = this[e] >> (i -= 8) & 255,
                i <= 0 && (i += this.DB,
                --e)),
                128 & n && (n |= -256),
                0 == r && (128 & this.s) != (128 & n) && ++r,
                (r > 0 || n != this.s) && (t[r++] = n);
        return t
    }
    ,
    n.prototype.equals = function(e) {
        return 0 == this.compareTo(e)
    }
    ,
    n.prototype.min = function(e) {
        return this.compareTo(e) < 0 ? this : e
    }
    ,
    n.prototype.max = function(e) {
        return this.compareTo(e) > 0 ? this : e
    }
    ,
    n.prototype.and = function(e) {
        var t = i();
        return this.bitwiseTo(e, m, t),
        t
    }
    ,
    n.prototype.or = function(e) {
        var t = i();
        return this.bitwiseTo(e, g, t),
        t
    }
    ,
    n.prototype.xor = function(e) {
        var t = i();
        return this.bitwiseTo(e, v, t),
        t
    }
    ,
    n.prototype.andNot = function(e) {
        var t = i();
        return this.bitwiseTo(e, y, t),
        t
    }
    ,
    n.prototype.not = function() {
        for (var e = i(), t = 0; t < this.t; ++t)
            e[t] = this.DM & ~this[t];
        return e.t = this.t,
        e.s = ~this.s,
        e
    }
    ,
    n.prototype.shiftLeft = function(e) {
        var t = i();
        return e < 0 ? this.rShiftTo(-e, t) : this.lShiftTo(e, t),
        t
    }
    ,
    n.prototype.shiftRight = function(e) {
        var t = i();
        return e < 0 ? this.lShiftTo(-e, t) : this.rShiftTo(e, t),
        t
    }
    ,
    n.prototype.getLowestSetBit = function() {
        for (var e = 0; e < this.t; ++e)
            if (0 != this[e])
                return e * this.DB + b(this[e]);
        return this.s < 0 ? this.t * this.DB : -1
    }
    ,
    n.prototype.bitCount = function() {
        for (var e = 0, t = this.s & this.DM, n = 0; n < this.t; ++n)
            e += _(this[n] ^ t);
        return e
    }
    ,
    n.prototype.testBit = function(e) {
        var t = Math.floor(e / this.DB);
        return t >= this.t ? 0 != this.s : !!(this[t] & 1 << e % this.DB)
    }
    ,
    n.prototype.setBit = function(e) {
        return this.changeBit(e, g)
    }
    ,
    n.prototype.clearBit = function(e) {
        return this.changeBit(e, y)
    }
    ,
    n.prototype.flipBit = function(e) {
        return this.changeBit(e, v)
    }
    ,
    n.prototype.add = function(e) {
        var t = i();
        return this.addTo(e, t),
        t
    }
    ,
    n.prototype.subtract = function(e) {
        var t = i();
        return this.subTo(e, t),
        t
    }
    ,
    n.prototype.multiply = function(e) {
        var t = i();
        return this.multiplyTo(e, t),
        t
    }
    ,
    n.prototype.divide = function(e) {
        var t = i();
        return this.divRemTo(e, t, null),
        t
    }
    ,
    n.prototype.remainder = function(e) {
        var t = i();
        return this.divRemTo(e, null, t),
        t
    }
    ,
    n.prototype.divideAndRemainder = function(e) {
        var t = i()
          , n = i();
        return this.divRemTo(e, t, n),
        new Array(t,n)
    }
    ,
    n.prototype.modPow = function(e, t) {
        var n, r, a = e.bitLength(), o = d(1);
        if (a <= 0)
            return o;
        n = a < 18 ? 1 : a < 48 ? 3 : a < 144 ? 4 : a < 768 ? 5 : 6,
        r = a < 8 ? new f(t) : t.isEven() ? new k(t) : new p(t);
        var s = new Array
          , l = 3
          , c = n - 1
          , u = (1 << n) - 1;
        if (s[1] = r.convert(this),
        n > 1) {
            var m = i();
            for (r.sqrTo(s[1], m); l <= u; )
                s[l] = i(),
                r.mulTo(m, s[l - 2], s[l]),
                l += 2
        }
        var g, v, y = e.t - 1, b = !0, _ = i();
        for (a = h(e[y]) - 1; y >= 0; ) {
            for (a >= c ? g = e[y] >> a - c & u : (g = (e[y] & (1 << a + 1) - 1) << c - a,
            y > 0 && (g |= e[y - 1] >> this.DB + a - c)),
            l = n; !(1 & g); )
                g >>= 1,
                --l;
            if ((a -= l) < 0 && (a += this.DB,
            --y),
            b)
                s[g].copyTo(o),
                b = !1;
            else {
                for (; l > 1; )
                    r.sqrTo(o, _),
                    r.sqrTo(_, o),
                    l -= 2;
                l > 0 ? r.sqrTo(o, _) : (v = o,
                o = _,
                _ = v),
                r.mulTo(_, s[g], o)
            }
            for (; y >= 0 && !(e[y] & 1 << a); )
                r.sqrTo(o, _),
                v = o,
                o = _,
                _ = v,
                --a < 0 && (a = this.DB - 1,
                --y)
        }
        return r.revert(o)
    }
    ,
    n.prototype.modInverse = function(e) {
        var t = e.isEven();
        if (this.isEven() && t || 0 == e.signum())
            return n.ZERO;
        for (var i = e.clone(), r = this.clone(), a = d(1), o = d(0), s = d(0), l = d(1); 0 != i.signum(); ) {
            for (; i.isEven(); )
                i.rShiftTo(1, i),
                t ? (a.isEven() && o.isEven() || (a.addTo(this, a),
                o.subTo(e, o)),
                a.rShiftTo(1, a)) : o.isEven() || o.subTo(e, o),
                o.rShiftTo(1, o);
            for (; r.isEven(); )
                r.rShiftTo(1, r),
                t ? (s.isEven() && l.isEven() || (s.addTo(this, s),
                l.subTo(e, l)),
                s.rShiftTo(1, s)) : l.isEven() || l.subTo(e, l),
                l.rShiftTo(1, l);
            i.compareTo(r) >= 0 ? (i.subTo(r, i),
            t && a.subTo(s, a),
            o.subTo(l, o)) : (r.subTo(i, r),
            t && s.subTo(a, s),
            l.subTo(o, l))
        }
        return 0 != r.compareTo(n.ONE) ? n.ZERO : l.compareTo(e) >= 0 ? l.subtract(e) : l.signum() < 0 ? (l.addTo(e, l),
        l.signum() < 0 ? l.add(e) : l) : l
    }
    ,
    n.prototype.pow = function(e) {
        return this.exp(e, new w)
    }
    ,
    n.prototype.gcd = function(e) {
        var t = this.s < 0 ? this.negate() : this.clone()
          , n = e.s < 0 ? e.negate() : e.clone();
        if (t.compareTo(n) < 0) {
            var i = t;
            t = n,
            n = i
        }
        var r = t.getLowestSetBit()
          , a = n.getLowestSetBit();
        if (a < 0)
            return t;
        for (r < a && (a = r),
        a > 0 && (t.rShiftTo(a, t),
        n.rShiftTo(a, n)); t.signum() > 0; )
            (r = t.getLowestSetBit()) > 0 && t.rShiftTo(r, t),
            (r = n.getLowestSetBit()) > 0 && n.rShiftTo(r, n),
            t.compareTo(n) >= 0 ? (t.subTo(n, t),
            t.rShiftTo(1, t)) : (n.subTo(t, n),
            n.rShiftTo(1, n));
        return a > 0 && n.lShiftTo(a, n),
        n
    }
    ,
    n.prototype.isProbablePrime = function(e) {
        var t, n = this.abs();
        if (1 == n.t && n[0] <= D[D.length - 1]) {
            for (t = 0; t < D.length; ++t)
                if (n[0] == D[t])
                    return !0;
            return !1
        }
        if (n.isEven())
            return !1;
        for (t = 1; t < D.length; ) {
            for (var i = D[t], r = t + 1; r < D.length && i < A; )
                i *= D[r++];
            for (i = n.modInt(i); t < r; )
                if (i % D[t++] == 0)
                    return !1
        }
        return n.millerRabin(e)
    }
    ,
    n.prototype.square = function() {
        var e = i();
        return this.squareTo(e),
        e
    }
    ,
    n.prototype.Barrett = k,
    null == S) {
        var L;
        if (S = new Array,
        M = 0,
        "undefined" != typeof window && window.crypto)
            if (window.crypto.getRandomValues) {
                var O = new Uint8Array(32);
                for (window.crypto.getRandomValues(O),
                L = 0; L < 32; ++L)
                    S[M++] = O[L]
            } else if ("Netscape" == navigator.appName && navigator.appVersion < "5") {
                var E = window.crypto.random(32);
                for (L = 0; L < E.length; ++L)
                    S[M++] = 255 & E.charCodeAt(L)
            }
        for (; M < Y; )
            L = Math.floor(65536 * Math.random()),
            S[M++] = L >>> 8,
            S[M++] = 255 & L;
        M = 0,
        T()
    }
    function P() {
        if (null == C) {
            for (T(),
            (C = new I).init(S),
            M = 0; M < S.length; ++M)
                S[M] = 0;
            M = 0
        }
        return C.next()
    }
    function j() {}
    function I() {
        this.i = 0,
        this.j = 0,
        this.S = new Array
    }
    j.prototype.nextBytes = function(e) {
        var t;
        for (t = 0; t < e.length; ++t)
            e[t] = P()
    }
    ,
    I.prototype.init = function(e) {
        var t, n, i;
        for (t = 0; t < 256; ++t)
            this.S[t] = t;
        for (n = 0,
        t = 0; t < 256; ++t)
            n = n + this.S[t] + e[t % e.length] & 255,
            i = this.S[t],
            this.S[t] = this.S[n],
            this.S[n] = i;
        this.i = 0,
        this.j = 0
    }
    ,
    I.prototype.next = function() {
        var e;
        return this.i = this.i + 1 & 255,
        this.j = this.j + this.S[this.i] & 255,
        e = this.S[this.i],
        this.S[this.i] = this.S[this.j],
        this.S[this.j] = e,
        this.S[e + this.S[this.i] & 255]
    }
    ;
    var Y = 256;
    module.exports = {
        default: n,
        BigInteger: n,
        SecureRandom: j
    }
}
)()