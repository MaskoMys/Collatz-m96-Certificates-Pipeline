#!/usr/bin/env python3
from fractions import Fraction


def ln_interval_rational(y: Fraction, N: int):
    z=(y-1)/(y+1)
    if z <= 0: raise ValueError
    s=Fraction(0,1); zpow=z; zz=z*z
    for j in range(N):
        if j>0: zpow*=zz
        s += zpow/(2*j+1)
    lower=2*s
    tail=2*(z**(2*N+1))/((2*N+1)*(1-z*z))
    return lower,lower+tail

def cf_fraction(x: Fraction,max_terms=10000):
    out=[]; y=x
    for _ in range(max_terms):
        a=y.numerator//y.denominator; out.append(a); r=y-a
        if r==0: break
        y=1/r
    return out

def convergent(cf):
    p0,p1=0,1; q0,q1=1,0
    for a in cf: p0,p1=p1,a*p1+p0; q0,q1=q1,a*q1+q0
    return p1,q1

def min_denominator_cert(A: Fraction,B: Fraction):
    assert A<B
    ca=cf_fraction(A); cb=cf_fraction(B)
    for i,(x,y) in enumerate(zip(ca,cb)):
        if x!=y:
            # Standard cylinder separator. Need careful endpoint order parity; this is source method.
            gamma_cf=ca[:i]+[min(x,y)+1]
            p,q=convergent(gamma_cf)
            return i,x,y,p,q
    raise RuntimeError

ln2L,ln2U=ln_interval_rational(Fraction(2),100)
ln3L,ln3U=ln_interval_rational(Fraction(3),100)
dL=ln3L/ln2U; dU=ln3U/ln2L
LOG2L=Fraction(693147,1000000)
deltaU_coarse=Fraction(317,200)
assert dL < dU
assert dU < deltaU_coarse
assert 3**200 < 2**317
X=1<<71
K_START=700000000000
K_STAGES=[K_START,5750934602875680,397560349370386783,4640282259296926456,27444133206411171953,77692117359936589403,205632218873398596256]
S_STAGES=[47,67,77,82,86,88]

def f_lower_coarse(s):
    return (deltaU_coarse-1)/(deltaU_coarse**s-1)

def suffix_step_bound(K,m_worst,s,cap=200):
    term=Fraction(3*(m_worst-s),X)
    min_vf=None
    for t in range(1,s+1):
        V=Fraction(t*K,m_worst)*f_lower_coarse(t)
        vf=V.numerator//V.denominator
        if V==vf: vf-=1
        assert vf>0
        min_vf=vf if min_vf is None else min(min_vf,vf)
        term += Fraction(3,(1<<min(vf,cap))-1)
    E=term/(3*K*LOG2L)
    return E,min_vf

def audit(m_worst):
    print('m_worst',m_worst)
    rows=[]
    for idx,s in enumerate(S_STAGES):
        K=K_STAGES[idx]
        E,mv=suffix_step_bound(K,m_worst,s)
        i,a,b,p,q=min_denominator_cert(dL,dU+E)
        ok=q>=K_STAGES[idx+1]
        # To certify implication to listed next threshold, interval needs no rational denom < threshold.
        # If min denominator q is >= target, okay; source had equality.
        rows.append((s,K,mv,float(E),i,a,b,q,K_STAGES[idx+1],ok))
        print(rows[-1])
    return rows

def main():
    results = {m: audit(m) for m in [95, 96, 98, 105]}
    if not all(row[-1] for row in results[96]):
        raise SystemExit('m=96 lower-bound audit failed')


if __name__ == '__main__':
    main()
