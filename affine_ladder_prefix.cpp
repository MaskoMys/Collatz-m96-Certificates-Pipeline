#include <gmpxx.h>
#include <iostream>
#include <vector>
#include <string>
#include <chrono>
#include <algorithm>
#include <cassert>
#include <cstdint>
#include <stdexcept>

using u64 = unsigned long long;
static const mpz_class X = mpz_class(1) << 71;
// Certified bracket from Paper 2: P28/Q28 < log_2 3 < P27/Q27.
static const mpz_class AL_LO_P("83130157078217"), AL_LO_Q("52449289519716");
static const mpz_class AL_HI_P("18340740190704"), AL_HI_Q("11571718688839");
static const u64 FIRST_POSITIVE_SURPLUS = 72057431991ULL;

mpz_class floor_div(const mpz_class& a,const mpz_class& b){ mpz_class q; mpz_fdiv_q(q.get_mpz_t(),a.get_mpz_t(),b.get_mpz_t()); return q; }
mpz_class ceil_div(const mpz_class& a,const mpz_class& b){ mpz_class q; mpz_cdiv_q(q.get_mpz_t(),a.get_mpz_t(),b.get_mpz_t()); return q; }
unsigned flog2(const mpz_class& n){ assert(n>0); return mpz_sizeinbase(n.get_mpz_t(),2)-1; }
unsigned v2(const mpz_class& n){ assert(n!=0); return mpz_scan1(n.get_mpz_t(),0); }
mpz_class mod2(const mpz_class& x,unsigned bits){ mpz_class r; mpz_fdiv_r_2exp(r.get_mpz_t(),x.get_mpz_t(),bits); return r; }

u64 floor_alpha(u64 n){
    mpz_class N(static_cast<unsigned long>(n));
    mpz_class lo=floor_div(AL_LO_P*N,AL_LO_Q), hi=floor_div(AL_HI_P*N,AL_HI_Q);
    if(lo!=hi) throw std::runtime_error("CF bracket does not decide floor(log2(3)*n)");
    return lo.get_ui();
}

struct Live{mpz_class L,U,r; unsigned bits; bool valid=true;};
bool normalize(Live& z){
 if(!z.valid||z.L>z.U){z.valid=false;return false;}
 z.r=mod2(z.r,z.bits); mpz_class M=mpz_class(1)<<z.bits;
 mpz_class first=z.r+ceil_div(z.L-z.r,M)*M;
 if(first>z.U){z.valid=false;return false;}
 mpz_class last=z.r+floor_div(z.U-z.r,M)*M;
 z.L=first;z.U=last;return true;
}
bool intsect_interval(Live& z,const mpz_class* L,const mpz_class* U){if(L&&*L>z.L)z.L=*L;if(U&&*U<z.U)z.U=*U;return normalize(z);}

bool intsect_linear_congruence(Live& z,const mpz_class& coef,const mpz_class& rhs,unsigned newbits){
 if(newbits<=z.bits){ if(mod2(coef*z.r-rhs,newbits)!=0){z.valid=false;return false;} return true; }
 mpz_class diff=mod2(rhs-coef*z.r,newbits);
 if(mod2(diff,z.bits)!=0){z.valid=false;return false;}
 unsigned d=newbits-z.bits; mpz_class rhs2=diff>>z.bits;
 mpz_class c2=mod2(coef,d), M=mpz_class(1)<<d, inv;
 if(mpz_invert(inv.get_mpz_t(),c2.get_mpz_t(),M.get_mpz_t())==0){z.valid=false;return false;}
 mpz_class t=mod2(rhs2*inv,d); z.r += (t<<z.bits); z.bits=newbits;
 return normalize(z);
}

struct CaseData{int m;mpz_class Anum,Aden;int depth;std::vector<mpz_class> extra;int k1max;std::vector<int> kcap;};
mpz_class cdiv(const mpz_class&a,unsigned long b){return ceil_div(a,mpz_class(b));}
CaseData make_case(int m){
 mpz_class term=cdiv(mpz_class(93)*(mpz_class(1)<<189),50);
 if(m==92){mpz_class B2=cdiv(mpz_class(17086)*(mpz_class(1)<<74),10000)+1;return{92,73,10,2,{0,X,B2,mpz_class(1)<<118},73,{0,73,118}};}
 if(m==93)return{93,15,1,3,{0,X,X,mpz_class(1)<<75,mpz_class(7)<<117},74,{0,74,118,188}};
 if(m==94)return{94,24,1,5,{0,X,X,X,mpz_class(1)<<75,mpz_class(1)<<119,mpz_class(1)<<189},75,{0,75,119,189,299,474}};
 if(m==95)return{95,24,1,6,{0,X,X,X,X,mpz_class(3)<<74,mpz_class(7)<<117,term},75,{0,75,119,189,299,474,751}};
 // The caps are rigorous consequences of k_{i+j} < alpha^j log2(n1+1),
 // n1 <= 29*2^71 < 2^76, and alpha < 317/200.
 if(m==96)return{96,29,1,7,{0,X,X,X,X,X,mpz_class(3)<<74,mpz_class(7)<<117,term},75,{0,75,120,191,303,481,763,1210}};
 throw std::runtime_error("unsupported case");
}

struct Search{
 CaseData c; int lo,hi; bool verbose; u64 enum_threshold; std::vector<int> fixedk;
 u64 nodes=0,finals=0,hits=0,hug_prunes=0,det_values=0,det_nodes=0;
 std::vector<u64> lev; std::vector<mpz_class> pow3;
 Search(CaseData cc,int l,int h,bool v,u64 th,std::vector<int> fk):c(std::move(cc)),lo(l),hi(h),verbose(v),enum_threshold(th),fixedk(std::move(fk)),lev(c.depth+1),pow3(1,1){}
 const mpz_class& p3(unsigned k){while(pow3.size()<=k)pow3.push_back(pow3.back()*3);return pow3[k];}
 std::pair<mpz_class,mpz_class> nrange(const Live&z,const mpz_class&p,const mpz_class&q,unsigned s,unsigned k){
   mpz_class mn=(((mpz_class(1)<<k)*(p*z.L+q))-(mpz_class(1)<<s))>>s;
   mpz_class mx=(((mpz_class(1)<<k)*(p*z.U+q))-(mpz_class(1)<<s))>>s; return{mn,mx};
 }
 bool linear_ge(Live&z,const mpz_class&C,const mpz_class&D){
   if(C>0){mpz_class L=ceil_div(-D,C);return intsect_interval(z,&L,nullptr);}
   if(C<0){mpz_class U=floor_div(D,-C);return intsect_interval(z,nullptr,&U);}
   if(D<0){z.valid=false;return false;} return true;
 }
 u64 live_count_capped(const Live& z,u64 cap) const {
   mpz_class n=(z.U-z.L)/(mpz_class(1)<<z.bits)+1;
   if(n>mpz_class(static_cast<unsigned long>(cap))) return cap+1; return n.get_ui();
 }
 // Once the live progression contains few actual a1 values, each continuation is
 // deterministic. This routine exactly simulates all of them; it is not a heuristic.
 void deterministic_finish(int i,unsigned k1,unsigned k,u64 Ksum,u64 Lsum,
                           const mpz_class&p,const mpz_class&q,unsigned s,const Live&live){
   mpz_class step=mpz_class(1)<<live.bits;
   for(mpz_class a=live.L; a<=live.U; a+=step){
     ++det_values;
     mpz_class num=p*a+q;
     if(mod2(num,s)!=0) throw std::runtime_error("internal nonintegral a_i");
     mpz_class ai=num>>s;
     if(!mpz_odd_p(ai.get_mpz_t())) throw std::runtime_error("internal even a_i");
     unsigned curk=k; u64 Ks=Ksum, Ls=Lsum;
     mpz_class n1=(a<<k1)-1;
     bool ok=true;
     for(int j=i;j<=c.depth;++j){
       ++det_nodes;
       mpz_class ni=(ai<<curk)-1;
       mpz_class v=ai*p3(curk)-1;
       unsigned ell=v2(v);
       if(ell<1){ok=false;break;}
       mpz_class nn=v>>ell;
       mpz_class need=std::max(c.extra.at(j+1),std::max(X,n1));
       if(nn<need){ok=false;break;}
       u64 Lnew=Ls+ell;
       if(Ks>=FIRST_POSITIVE_SURPLUS) throw std::runtime_error("prefix beyond frontier theorem");
       if(Ks+Lnew>floor_alpha(Ks)){++hug_prunes;ok=false;break;}
       if(j==c.depth){ if(ok) ++hits; break; }
       unsigned kn=v2(nn+1);
       if(kn<1 || kn>(unsigned)c.kcap.at(j+1)){ok=false;break;}
       ai=(nn+1)>>kn;
       if(!mpz_odd_p(ai.get_mpz_t())){ok=false;break;}
       curk=kn; Ks+=kn; Ls=Lnew;
     }
   }
 }
 void rec(int i,unsigned k1,unsigned k,u64 Ksum,u64 Lsum,const mpz_class&p,const mpz_class&q,unsigned s,const Live&live){
  ++nodes;
  u64 cnt=live_count_capped(live,enum_threshold);
  if(cnt<=enum_threshold){deterministic_finish(i,k1,k,Ksum,Lsum,p,q,s,live);return;}
  auto rr=nrange(live,p,q,s,k); mpz_class nimax=rr.second;
  mpz_class n1min=(live.L<<k1)-1, extra=c.extra.at(i+1), nlb=std::max(extra,std::max(X,n1min));
  mpz_class T=(p3(k)*(nimax+1)-(mpz_class(1)<<k))/((mpz_class(1)<<k)*nlb);
  if(T<2)return; unsigned ellmax=flog2(T); mpz_class pk=p3(k);
  for(unsigned ell=1;ell<=ellmax;++ell){
   const u64 Lnew=Lsum+ell;
   if(Ksum>=FIRST_POSITIVE_SURPLUS) throw std::runtime_error("prefix beyond frontier theorem");
   if(Ksum+Lnew>floor_alpha(Ksum)){++hug_prunes;continue;}
   Live z=live; mpz_class denom=pk*p;
   mpz_class Lb=ceil_div(extra*(mpz_class(1)<<(s+ell))+(mpz_class(1)<<s)-pk*q,denom);
   if(!intsect_interval(z,&Lb,nullptr))continue;
   mpz_class C=pk*p-(mpz_class(1)<<(k1+s+ell));
   mpz_class D=pk*q-(mpz_class(1)<<s)+(mpz_class(1)<<(s+ell));
   if(!linear_ge(z,C,D))continue;
   mpz_class nmax=(pk*(p*z.U+q)-(mpz_class(1)<<s))>>(s+ell);
   if(i==c.depth){
     ++finals; unsigned b=s+ell+1;
     mpz_class rhs=(mpz_class(1)<<(s+ell))+(mpz_class(1)<<s)-pk*q;
     if(intsect_linear_congruence(z,pk*p,rhs,b))++hits;
     continue;
   }
   int kmax=std::min<int>(flog2(nmax+1),c.kcap.at(i+1));
   mpz_class p2=pk*p, qbase=pk*q+((mpz_class(1)<<ell)-1)*(mpz_class(1)<<s);
   // Enumerate exact 2-adic valuations by following a single Hensel-lift path.
   // This is equivalent to testing every kn, but requires only one inversion and
   // then one binary split per nonempty valuation level.
   const unsigned baseExp=s+ell;
   unsigned E=baseExp+1; // kn=1
   Live cont=z;
   if(!intsect_linear_congruence(cont,p2,-qbase,E)) continue; // v2(y)>=E
   for(int kn=1;kn<=kmax && cont.valid;++kn,++E){
     // cont has y=p2*a+qbase divisible by 2^E and is one class mod 2^E.
     if(cont.bits!=E) throw std::runtime_error("unexpected Hensel precision");
     mpz_class yr=p2*cont.r+qbase;
     unsigned bit=mpz_tstbit(yr.get_mpz_t(),E); // bit for lift a=cont.r
     Live exact=cont, next=cont;
     exact.bits=E+1; next.bits=E+1;
     // Adding 2^E to a toggles the E-th bit because p2 is odd.
     if(bit==0){ exact.r += (mpz_class(1)<<E); }
     else      { next.r  += (mpz_class(1)<<E); }
     bool exok=normalize(exact); bool nxok=normalize(next);
     if(exok && (i+1 >= (int)fixedk.size() || fixedk[i+1]==0 || fixedk[i+1]==kn)){
       unsigned s2=E;
       ++lev[i]; rec(i+1,k1,kn,Ksum+kn,Lnew,p2,qbase,s2,exact);
     }
     if(!nxok) break;
     cont=std::move(next);
   }
  }
 }
 void run(){
  for(u64 n=1;n<=100000;n++) (void)floor_alpha(n);
  auto st=std::chrono::steady_clock::now(); mpz_class U1=(c.Anum*X)/c.Aden;
  for(int k1=lo;k1<=hi;++k1){
   mpz_class L=ceil_div(X+1,mpz_class(1)<<k1),U=(U1+1)/(mpz_class(1)<<k1);
   Live z{L,U,1,1,true}; u64 n0=nodes,f0=finals,h0=hits,p0=hug_prunes,d0=det_values;
   if(normalize(z))rec(1,k1,k1,k1,0,1,0,0,z);
   if(verbose)std::cout<<"k1="<<k1<<" nodes="<<nodes-n0<<" det_values="<<det_values-d0
     <<" hug_prunes="<<hug_prunes-p0<<" final="<<finals-f0<<" hits="<<hits-h0<<"\n"<<std::flush;
  }
  double sec=std::chrono::duration<double>(std::chrono::steady_clock::now()-st).count();
  std::cout<<"CASE="<<c.m<<" K1_RANGE="<<lo<<".."<<hi<<" NODES="<<nodes
    <<" DET_VALUES="<<det_values<<" DET_NODES="<<det_nodes<<" HUG_PRUNES="<<hug_prunes;
  for(int i=1;i<c.depth;++i)std::cout<<" LEVEL"<<i<<"="<<lev[i];
  std::cout<<" FINAL_INTERVALS="<<finals<<" HITS="<<hits<<" SECONDS="<<sec<<"\nRESULT: "<<(hits==0?"PASS":"FAIL")<<"\n";
 }
};
int main(int ac,char**av){
 if(ac<3){std::cerr<<"usage: prog m prefix_csv [verbose [enum_threshold]]\n";return 2;}
 int m=std::stoi(av[1]); auto c=make_case(m); std::string ps=av[2];
 std::vector<int> fk(c.depth+2,0); size_t pos=0; int idx=1;
 while(pos<=ps.size() && idx<(int)fk.size()){
   size_t q=ps.find(',',pos); std::string tok=ps.substr(pos,q==std::string::npos?std::string::npos:q-pos);
   if(!tok.empty() && tok!="*") fk[idx]=std::stoi(tok);
   ++idx; if(q==std::string::npos) break; pos=q+1;
 }
 int lo=fk[1]?fk[1]:1, hi=fk[1]?fk[1]:c.k1max;
 bool v=ac>3?std::stoi(av[3]):false; u64 th=ac>4?std::stoull(av[4]):256;
 Search(c,lo,hi,v,th,fk).run();
}
