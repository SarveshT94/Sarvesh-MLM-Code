"use client";

import { useEffect, useState, useRef } from "react";
import useAuthStore from "@/store/authStore";
import { useRouter } from "next/navigation";
import { requestProfileUpdate, verifyProfileOtp } from "@/services/profile";
import { fetchWalletData, submitWithdrawal, submitP2PTransfer } from "@/services/wallet";
import { fetchNetworkData, fetchUplineData } from "@/services/team";
import Storefront from "@/components/store/Storefront";
import MyStoreOrders from "@/components/store/MyStoreOrders";
import MyTeam from "@/components/team/MyTeam";
import { fetchPackages, purchasePlan, fetchCompensationPlan, fetchUserOrders } from "@/services/package";
import { fetchUserRank } from "@/services/gamification"; 
import { fetchTickets, createTicket } from "@/services/support"; 
import { fetchKycData, submitKycData } from "@/services/kyc"; 
import { 
  LayoutDashboard, UserCircle, Users, ShoppingBag, 
  Wallet, LogOut, Share2, Copy, CheckCircle2, TrendingUp, Camera, ShieldCheck, 
  AlertCircle, Loader2, GitMerge, UserPlus, X, Zap, BarChart3, Target, Globe, 
  RefreshCw, Download, Receipt, Printer, ArrowRightLeft, LifeBuoy, Award, Plus, 
  MessageSquare, Image as ImageIcon, Info, FileCheck, UploadCloud, ChevronRight, 
  UserMinus, Building, MapPin, Mail, Phone, ListTree
} from "lucide-react";

export default function DashboardPage() {
  const { user, isAuthenticated, isChecking, logout, setAuth } = useAuthStore();
  const router = useRouter();
  
  const [activeTab, setActiveTab] = useState("Overview"); 
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!isChecking && !isAuthenticated) router.push("/login");
  }, [isAuthenticated, isChecking, router]);

  useEffect(() => {
    const savedTab = sessionStorage.getItem("dashboardTab");
    if (savedTab) setActiveTab(savedTab);
  }, []);

  const switchTab = (tabName) => {
    setActiveTab(tabName);
    sessionStorage.setItem("dashboardTab", tabName);
  };

  if (isChecking || !isAuthenticated || !user) return null;

  const refCode = user?.referral_code || "PENDING";
  const shareUrl = `http://localhost:3000/register?ref=${refCode}`;

  const handleShare = async () => {
    const shareData = { title: 'Join my RK Trendz Network!', text: `Sign up using my referral code: ${refCode} and join my team!`, url: shareUrl };
    try { if (navigator.share) await navigator.share(shareData); else handleCopy(); } catch (err) { console.error("Error sharing:", err); }
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(shareUrl);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const menuItems = [
    { name: "Overview", icon: LayoutDashboard },
    { name: "Company Info", icon: Building },
    { name: "My Profile", icon: UserCircle },
    { name: "KYC Verification", icon: FileCheck },
    { name: "My Network Tree", icon: Users },
    { name: "Wallet & Payouts", icon: Wallet },
    { name: "Product Catalog", label: "Shop", icon: ShoppingBag },
    { name: "My Orders & Invoices", label: "My Orders", icon: Receipt },
    { name: "Help & Support", icon: LifeBuoy },
  ];

  // ---------------------------------------------------------
  // 1. OVERVIEW TAB
  // ---------------------------------------------------------
  const OverviewTab = () => {
    const [rankData, setRankData] = useState({
      current_rank: "Loading...", next_rank: "Loading...",
      current_volume: 0, next_rank_volume: 0, progress_percentage: 0
    });

    useEffect(() => {
      const loadRank = async () => {
        const res = await fetchUserRank();
        if (res.success && res.data) setRankData(res.data);
      };
      loadRank();
    }, []);

    return (
      <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
        <div className="relative bg-white rounded-[2rem] p-8 shadow-[0_8px_30px_rgb(0,0,0,0.04)] border border-slate-100 overflow-hidden print:hidden">
          <div className="absolute top-0 right-0 w-64 h-64 bg-emerald-500/10 rounded-full blur-3xl -translate-y-1/2 translate-x-1/3 pointer-events-none"></div>
          <div className="absolute bottom-0 left-0 w-48 h-48 bg-blue-500/10 rounded-full blur-3xl translate-y-1/2 -translate-x-1/4 pointer-events-none"></div>
          <div className="relative z-10">
            <h2 className="text-3xl font-black text-slate-900 tracking-tight">Welcome back, {user.full_name.split(' ')[0]}! 👋</h2>
            <p className="mt-2 text-slate-500 font-medium">Here is your network and financial overview for today.</p>
          </div>
        </div>

        <div className="bg-gradient-to-br from-slate-900 via-slate-800 to-indigo-950 rounded-[2rem] shadow-xl border border-slate-800 p-8 text-white print:hidden relative overflow-hidden group">
          <div className="absolute inset-0 opacity-10 mix-blend-overlay" style={{backgroundImage: `url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23ffffff' fill-opacity='1'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E")`}}></div>
          <div className="relative z-10">
            <div className="flex flex-col md:flex-row md:justify-between md:items-end gap-6 mb-6">
              <div className="flex items-center">
                <div className="p-3 bg-white/10 rounded-2xl mr-4 backdrop-blur-md shadow-inner border border-white/5 group-hover:scale-110 transition-transform"><Award className="h-8 w-8 text-amber-400" /></div>
                <div>
                  <p className="text-xs text-slate-300 font-bold uppercase tracking-[0.2em] mb-1">Current Rank</p>
                  <h3 className="font-black text-3xl text-white tracking-tight drop-shadow-md">{rankData.current_rank}</h3>
                </div>
              </div>
              {rankData.next_rank !== "Max Rank Reached" && (
                <div className="px-4 py-2 bg-white/10 border border-white/20 rounded-xl backdrop-blur-md shadow-lg flex items-center">
                  <Target className="h-4 w-4 mr-2 text-emerald-400" />
                  <span className="text-sm font-bold text-slate-100">Next Goal: {rankData.next_rank}</span>
                </div>
              )}
            </div>
            
            <div className="w-full bg-slate-950/50 border border-slate-700/50 rounded-full h-4 mb-3 overflow-hidden shadow-inner relative">
              <div className="bg-gradient-to-r from-emerald-400 via-emerald-500 to-teal-400 h-full rounded-full relative transition-all duration-1000 ease-out shadow-[0_0_15px_rgba(16,185,129,0.5)]" style={{width: `${rankData.progress_percentage}%`}}>
                <div className="absolute inset-0 bg-white/20 animate-[pulse_2s_ease-in-out_infinite]"></div>
              </div>
            </div>
            <div className="flex justify-between items-center text-sm font-semibold">
              <span className="text-emerald-400 flex items-center"><TrendingUp className="h-4 w-4 mr-1"/> ₹{rankData.current_volume.toLocaleString('en-IN')} Vol.</span>
              <span className="text-slate-400">
                {rankData.next_rank !== "Max Rank Reached" ? `₹${rankData.next_rank_volume.toLocaleString('en-IN')} Target` : "Maximum Rank Achieved!"}
              </span>
            </div>
          </div>
          <Globe className="absolute -right-10 -bottom-10 h-64 w-64 text-white/5 rotate-12 group-hover:rotate-45 transition-transform duration-1000" />
        </div>

        <div className="grid grid-cols-1 gap-6 sm:grid-cols-3 mb-8 print:hidden">
          {[
            { title: "Total Wallet Balance", value: "Check Wallet", icon: Wallet, color: "emerald", tab: "Wallet & Payouts", btnText: "Request Withdrawal" },
            { title: "Active Downline", value: "View Network", icon: Users, color: "blue", tab: "My Network Tree", btnText: "View Network Tree" },
            { title: "Current Plan", value: "Free Tier", icon: CheckCircle2, color: "purple", tab: "Product Catalog", btnText: "Shop & Activate" }
          ].map((card, idx) => (
            <div key={idx} className="bg-white overflow-hidden shadow-[0_8px_30px_rgb(0,0,0,0.04)] hover:shadow-xl transition-all duration-300 hover:-translate-y-1 border border-slate-100 rounded-[2rem] group">
              <div className="p-6">
                <div className="flex items-center">
                  <div className={`flex-shrink-0 bg-${card.color}-50 rounded-2xl p-4 group-hover:bg-${card.color}-100 transition-colors`}>
                    <card.icon className={`h-7 w-7 text-${card.color}-600`} />
                  </div>
                  <div className="ml-5 w-0 flex-1">
                    <dl>
                      <dt className="text-sm font-semibold text-slate-500 truncate">{card.title}</dt>
                      <dd className="text-2xl font-black text-slate-900 mt-1">{card.value}</dd>
                    </dl>
                  </div>
                </div>
              </div>
              <div className="bg-slate-50 px-6 py-4 border-t border-slate-100">
                <button onClick={() => switchTab(card.tab)} className={`text-sm font-bold text-${card.color}-600 hover:text-${card.color}-800 flex items-center w-full justify-between group-hover:pl-2 transition-all`}>
                  {card.btnText} <ChevronRight className="h-4 w-4" />
                </button>
              </div>
            </div>
          ))}
        </div>

        <div className="bg-white rounded-[2rem] shadow-[0_8px_30px_rgb(0,0,0,0.04)] border border-slate-100 p-8 lg:w-2/3 print:hidden relative overflow-hidden">
          <div className="absolute top-0 right-0 bg-slate-50 w-full h-full transform skew-x-12 translate-x-1/2"></div>
          <div className="relative z-10">
            <h3 className="text-xl font-black text-slate-900 mb-2">Grow Your Network</h3>
            <p className="text-sm font-medium text-slate-500 mb-6">Share your unique referral code. Earn commissions when friends join and activate.</p>
            <div className="flex flex-col sm:flex-row gap-4">
              <div className="flex-1 bg-white border-2 border-slate-100 rounded-2xl p-4 flex items-center justify-between shadow-inner">
                <div><p className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-1">Your Referral Code</p><p className="text-2xl font-black text-emerald-600 tracking-[0.15em]">{refCode}</p></div>
                <button onClick={handleCopy} disabled={refCode === "PENDING"} className="p-3 bg-slate-50 border border-slate-200 rounded-xl hover:bg-emerald-50 hover:text-emerald-600 hover:border-emerald-200 transition-all shadow-sm text-slate-600 disabled:opacity-50">{copied ? <CheckCircle2 className="h-6 w-6 text-emerald-500" /> : <Copy className="h-6 w-6" />}</button>
              </div>
              <button onClick={handleShare} disabled={refCode === "PENDING"} className="flex items-center justify-center px-8 py-4 bg-slate-900 hover:bg-slate-800 text-white font-bold rounded-2xl shadow-lg hover:shadow-xl transition-all sm:w-auto disabled:opacity-50 hover:-translate-y-0.5"><Share2 className="mr-2 h-5 w-5" /> Share Link</button>
            </div>
          </div>
        </div>
      </div>
    );
  };

  // ---------------------------------------------------------
  // 2. COMPANY PROFILE TAB
  // ---------------------------------------------------------
  const CompanyProfileTab = () => {
    return (
      <div className="max-w-6xl mx-auto space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
        <div className="mb-8">
          <h2 className="text-3xl font-black text-slate-900 tracking-tight">Company Overview</h2>
          <p className="text-slate-500 font-medium mt-1">Official information, legal compliance, and contact details.</p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          <div className="lg:col-span-2 space-y-8">
            <div className="bg-white rounded-[2rem] shadow-[0_8px_30px_rgb(0,0,0,0.04)] border border-slate-100 p-8 md:p-10 relative overflow-hidden">
              <div className="absolute top-0 right-0 w-64 h-64 bg-indigo-500/10 rounded-full blur-3xl -translate-y-1/2 translate-x-1/3"></div>
              <h3 className="text-2xl font-black text-slate-900 mb-4 flex items-center"><Building className="h-6 w-6 text-indigo-500 mr-3"/> RK Trendz Pvt. Ltd.</h3>
              <p className="text-slate-600 leading-relaxed font-medium mb-6">
                RK Trendz is a premier Direct Selling and Network Marketing platform dedicated to empowering individuals through world-class digital products and transparent earning opportunities. We adhere strictly to the highest standards of corporate governance and MLM compliance in India.
              </p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="bg-slate-50 p-5 rounded-2xl border border-slate-100">
                  <p className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-1">Company Identity Number (CIN)</p>
                  <p className="text-lg font-black text-slate-800 font-mono">U72900MH2024PTC000000</p>
                </div>
                <div className="bg-slate-50 p-5 rounded-2xl border border-slate-100">
                  <p className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-1">GST Identification Number</p>
                  <p className="text-lg font-black text-slate-800 font-mono">27AAACR0000A1Z5</p>
                </div>
              </div>
            </div>

            <div className="bg-white rounded-[2rem] shadow-[0_8px_30px_rgb(0,0,0,0.04)] border border-slate-100 p-8 md:p-10">
              <h3 className="text-xl font-black text-slate-900 mb-6 border-b border-slate-100 pb-4">Head Office & Contact</h3>
              <div className="space-y-6">
                <div className="flex items-start">
                  <div className="bg-indigo-50 p-3 rounded-xl mr-4"><MapPin className="h-6 w-6 text-indigo-600" /></div>
                  <div>
                    <h4 className="font-bold text-slate-900">Registered Corporate Office</h4>
                    <p className="text-slate-500 mt-1">101, Business Park Tower A,<br/>Andheri East, Mumbai, Maharashtra 400069<br/>India</p>
                  </div>
                </div>
                <div className="flex items-start">
                  <div className="bg-emerald-50 p-3 rounded-xl mr-4"><Mail className="h-6 w-6 text-emerald-600" /></div>
                  <div>
                    <h4 className="font-bold text-slate-900">Official Support</h4>
                    <p className="text-slate-500 mt-1">support@rktrendz.com</p>
                  </div>
                </div>
                <div className="flex items-start">
                  <div className="bg-amber-50 p-3 rounded-xl mr-4"><Phone className="h-6 w-6 text-amber-600" /></div>
                  <div>
                    <h4 className="font-bold text-slate-900">Helpline</h4>
                    <p className="text-slate-500 mt-1">+91 1800-123-4567 (Mon-Sat, 10AM - 6PM)</p>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div className="lg:col-span-1 space-y-8">
            <div className="bg-gradient-to-br from-slate-900 to-slate-800 rounded-[2rem] shadow-xl border border-slate-700 p-8 text-white">
              <h3 className="text-xl font-black mb-4 flex items-center"><ShieldCheck className="h-6 w-6 text-emerald-400 mr-2"/> Legal Documents</h3>
              <p className="text-slate-400 text-sm mb-6">Download our official compliance and incorporation certificates.</p>
              <div className="space-y-3">
                <button className="w-full flex items-center justify-between p-4 bg-white/10 hover:bg-white/20 border border-white/10 rounded-xl transition-all">
                  <span className="font-bold text-sm">Certificate of Incorporation</span>
                  <Download className="h-4 w-4" />
                </button>
                <button className="w-full flex items-center justify-between p-4 bg-white/10 hover:bg-white/20 border border-white/10 rounded-xl transition-all">
                  <span className="font-bold text-sm">GST Certificate</span>
                  <Download className="h-4 w-4" />
                </button>
                <button className="w-full flex items-center justify-between p-4 bg-white/10 hover:bg-white/20 border border-white/10 rounded-xl transition-all">
                  <span className="font-bold text-sm">Terms & Conditions</span>
                  <Download className="h-4 w-4" />
                </button>
              </div>
            </div>

            <div className="bg-indigo-50 rounded-[2rem] border border-indigo-100 p-8 text-center">
              <div className="w-16 h-16 bg-white rounded-full flex items-center justify-center shadow-sm mx-auto mb-4"><LifeBuoy className="h-8 w-8 text-indigo-500" /></div>
              <h4 className="font-black text-slate-900 mb-2">Need Assistance?</h4>
              <p className="text-sm text-slate-600 mb-6">Our dedicated support team is available to resolve your queries.</p>
              <button onClick={() => switchTab("Help & Support")} className="w-full py-3 bg-indigo-600 hover:bg-indigo-700 text-white font-bold rounded-xl shadow-md transition-all">
                Open Support Ticket
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  };

  // ---------------------------------------------------------
  // 3. PROFILE TAB
  // ---------------------------------------------------------
  const ProfileTab = () => {
    const currentEmail = user.email || "";
    const currentPhone = user.phone || "";
    const [userRank, setUserRank] = useState("Distributor");

    const [form, setForm] = useState({ email: currentEmail, phone: currentPhone });
    const [personalForm, setPersonalForm] = useState({ dob: "", gender: "male", address: "", city: "", state: "", pincode: "" });
    const [familyForm, setFamilyForm] = useState({ nomineeName: "", nomineeRelation: "" });
    
    const [photoPreview, setPhotoPreview] = useState(null);
    const fileInputRef = useRef(null);
    const [activeVerification, setActiveVerification] = useState(null);
    const [otpCode, setOtpCode] = useState("");
    const [isLoading, setIsLoading] = useState(false);
    const [status, setStatus] = useState({ type: "", msg: "" });

    const isEmailChanged = form.email !== currentEmail && form.email.includes("@");
    const isPhoneChanged = form.phone !== currentPhone && form.phone.length >= 10;

    useEffect(() => {
      const loadData = async () => {
        const rankRes = await fetchUserRank();
        if (rankRes.success && rankRes.data) setUserRank(rankRes.data.current_rank);
      };
      loadData();
    }, []);

    const handlePhotoChange = (e) => {
      const file = e.target.files[0];
      if (file) {
        const reader = new FileReader();
        reader.onloadend = () => setPhotoPreview(reader.result);
        reader.readAsDataURL(file);
      }
    };

    const handleRequestOtp = async (type) => {
      setStatus({ type: "", msg: "" }); setIsLoading(true);
      const newIdentifier = type === 'email' ? form.email : form.phone;
      const res = await requestProfileUpdate(type, newIdentifier);
      if (res.success) { setStatus({ type: "success", msg: res.data.message }); setActiveVerification(type); } 
      else { setStatus({ type: "error", msg: res.message }); }
      setIsLoading(false);
    };

    const handleVerifyOtp = async () => {
      if (otpCode.length !== 6) return setStatus({ type: "error", msg: "Please enter a valid 6-digit OTP." });
      setIsLoading(true); setStatus({ type: "", msg: "" });
      const res = await verifyProfileOtp(otpCode);
      if (res.success) {
        setStatus({ type: "success", msg: res.data.message });
        setAuth({ ...user, [activeVerification]: form[activeVerification] });
        setActiveVerification(null); setOtpCode("");
      } else { setStatus({ type: "error", msg: res.message }); }
      setIsLoading(false);
    };

    const saveGeneralDetails = (e) => {
      e.preventDefault();
      setStatus({ type: "success", msg: "Personal & Family details updated successfully!" });
      setTimeout(() => setStatus({type: "", msg: ""}), 3000);
    }

    return (
      <div className="max-w-6xl mx-auto space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
        {status.msg && (
          <div className={`p-4 rounded-xl border-l-4 shadow-sm flex items-center ${status.type === 'error' ? 'bg-red-50 border-red-500 text-red-700' : 'bg-emerald-50 border-emerald-500 text-emerald-700'}`}>
            {status.type === 'error' ? <AlertCircle className="h-6 w-6 mr-3" /> : <ShieldCheck className="h-6 w-6 mr-3" />}
            <p className="font-bold">{status.msg}</p>
          </div>
        )}

        <div className="grid grid-cols-1 xl:grid-cols-3 gap-8">
          <div className="xl:col-span-1 space-y-6">
            <div className="bg-white rounded-[2rem] shadow-[0_8px_30px_rgb(0,0,0,0.04)] border border-slate-100 p-8 text-center relative overflow-hidden">
              <div className="absolute top-0 inset-x-0 h-32 bg-gradient-to-b from-slate-50 to-white border-b border-slate-100"></div>
              <div className="relative inline-block mb-4 group cursor-pointer" onClick={() => fileInputRef.current.click()}>
                <div className="h-40 w-40 rounded-full overflow-hidden border-8 border-white bg-slate-100 shadow-xl relative z-10">
                  {photoPreview ? <img src={photoPreview} alt="Profile" className="h-full w-full object-cover" /> : <div className="h-full w-full flex items-center justify-center bg-gradient-to-br from-emerald-100 to-teal-100 text-emerald-600 text-5xl font-black">{user.full_name.charAt(0).toUpperCase()}</div>}
                </div>
                <div className="absolute inset-0 bg-slate-900/40 rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity z-20"><Camera className="h-10 w-10 text-white" /></div>
                <input type="file" ref={fileInputRef} onChange={handlePhotoChange} accept="image/*" className="hidden" />
              </div>
              <h3 className="text-2xl font-black text-slate-900 tracking-tight">{user.full_name}</h3>
              <p className="text-sm font-bold text-emerald-600 bg-emerald-50 inline-flex items-center px-4 py-1.5 rounded-full mt-3 border border-emerald-100">
                <Award className="h-4 w-4 mr-1.5" /> Rank: {userRank}
              </p>
            </div>

            <div className="bg-white rounded-[2rem] shadow-[0_8px_30px_rgb(0,0,0,0.04)] border border-slate-100 overflow-hidden">
              <div className="px-8 py-6 border-b border-slate-100 bg-slate-50/50"><h3 className="font-bold text-slate-900 flex items-center"><ShieldCheck className="h-5 w-5 mr-2 text-slate-400" /> Account Security</h3></div>
              <div className="p-8 space-y-6">
                <div className="space-y-2">
                  <label className="text-xs font-bold text-slate-500 uppercase tracking-wider">Email Address</label>
                  <div className="flex gap-2">
                    <input type="email" value={form.email} disabled={activeVerification === 'email'} onChange={(e) => setForm({ ...form, email: e.target.value })} className="flex-1 px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl font-medium focus:ring-2 focus:ring-emerald-500" />
                    <button onClick={() => handleRequestOtp('email')} disabled={!isEmailChanged || isLoading || activeVerification === 'email'} className="px-6 py-3 font-bold rounded-xl transition-all bg-slate-900 hover:bg-slate-800 text-white disabled:opacity-50 disabled:bg-slate-100 disabled:text-slate-400">Update</button>
                  </div>
                  {activeVerification === 'email' && (
                    <div className="mt-2 flex gap-2"><input type="text" maxLength="6" placeholder="6-digit OTP" value={otpCode} onChange={(e) => setOtpCode(e.target.value)} className="flex-1 px-4 py-3 text-center font-mono border rounded-xl focus:ring-2 focus:ring-emerald-500" /><button onClick={handleVerifyOtp} className="px-6 bg-emerald-600 hover:bg-emerald-700 text-white font-bold rounded-xl transition-colors">Verify</button></div>
                  )}
                </div>
                <hr className="border-slate-100" />
                <div className="space-y-2">
                  <label className="text-xs font-bold text-slate-500 uppercase tracking-wider">Phone Number</label>
                  <div className="flex gap-2">
                    <input type="text" value={form.phone} disabled={activeVerification === 'phone'} onChange={(e) => setForm({ ...form, phone: e.target.value })} className="flex-1 px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl font-medium focus:ring-2 focus:ring-emerald-500" />
                    <button onClick={() => handleRequestOtp('phone')} disabled={!isPhoneChanged || isLoading || activeVerification === 'phone'} className="px-6 py-3 font-bold rounded-xl transition-all bg-slate-900 hover:bg-slate-800 text-white disabled:opacity-50 disabled:bg-slate-100 disabled:text-slate-400">Update</button>
                  </div>
                  {activeVerification === 'phone' && (
                    <div className="mt-2 flex gap-2"><input type="text" maxLength="6" placeholder="6-digit OTP" value={otpCode} onChange={(e) => setOtpCode(e.target.value)} className="flex-1 px-4 py-3 text-center font-mono border rounded-xl focus:ring-2 focus:ring-emerald-500" /><button onClick={handleVerifyOtp} className="px-6 bg-emerald-600 hover:bg-emerald-700 text-white font-bold rounded-xl transition-colors">Verify</button></div>
                  )}
                </div>
              </div>
            </div>
          </div>

          <div className="xl:col-span-2 space-y-6">
            <form onSubmit={saveGeneralDetails} className="bg-white rounded-[2rem] shadow-[0_8px_30px_rgb(0,0,0,0.04)] border border-slate-100 overflow-hidden">
              <div className="px-8 py-6 border-b border-slate-100 bg-slate-50/50 flex items-center justify-between">
                <h3 className="text-xl font-bold text-slate-900">Personal & Family Details</h3>
                <span className="text-xs font-bold bg-slate-200 text-slate-600 px-3 py-1 rounded-full">Optional</span>
              </div>
              <div className="p-8 space-y-8">
                <div className="space-y-5">
                  <h4 className="text-sm font-bold text-slate-400 uppercase tracking-wider border-b border-slate-100 pb-3">General Information</h4>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                    <div><label className="block text-sm font-bold text-slate-700 mb-2">Date of Birth</label><input type="date" value={personalForm.dob} onChange={(e) => setPersonalForm({...personalForm, dob: e.target.value})} className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl font-medium focus:ring-2 focus:ring-slate-900" /></div>
                    <div><label className="block text-sm font-bold text-slate-700 mb-2">Gender</label><select value={personalForm.gender} onChange={(e) => setPersonalForm({...personalForm, gender: e.target.value})} className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl font-medium focus:ring-2 focus:ring-slate-900"><option value="male">Male</option><option value="female">Female</option><option value="other">Other</option></select></div>
                    <div className="md:col-span-2"><label className="block text-sm font-bold text-slate-700 mb-2">Full Address</label><input type="text" placeholder="Street, Landmark, Area" value={personalForm.address} onChange={(e) => setPersonalForm({...personalForm, address: e.target.value})} className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl font-medium focus:ring-2 focus:ring-slate-900" /></div>
                    <div><label className="block text-sm font-bold text-slate-700 mb-2">City / District</label><input type="text" placeholder="City" value={personalForm.city} onChange={(e) => setPersonalForm({...personalForm, city: e.target.value})} className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl font-medium focus:ring-2 focus:ring-slate-900" /></div>
                    <div className="flex gap-4">
                      <div className="flex-1"><label className="block text-sm font-bold text-slate-700 mb-2">State</label><input type="text" placeholder="State" value={personalForm.state} onChange={(e) => setPersonalForm({...personalForm, state: e.target.value})} className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl font-medium focus:ring-2 focus:ring-slate-900" /></div>
                      <div className="w-1/3"><label className="block text-sm font-bold text-slate-700 mb-2">PIN Code</label><input type="text" placeholder="000000" value={personalForm.pincode} onChange={(e) => setPersonalForm({...personalForm, pincode: e.target.value})} className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl font-medium focus:ring-2 focus:ring-slate-900" /></div>
                    </div>
                  </div>
                </div>

                <div className="space-y-5 pt-4">
                  <h4 className="text-sm font-bold text-slate-400 uppercase tracking-wider border-b border-slate-100 pb-3">Nominee Details</h4>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                    <div><label className="block text-sm font-bold text-slate-700 mb-2">Nominee Full Name</label><input type="text" placeholder="Name" value={familyForm.nomineeName} onChange={(e) => setFamilyForm({...familyForm, nomineeName: e.target.value})} className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl font-medium focus:ring-2 focus:ring-slate-900" /></div>
                    <div><label className="block text-sm font-bold text-slate-700 mb-2">Relation to User</label><input type="text" placeholder="e.g. Spouse, Child, Parent" value={familyForm.nomineeRelation} onChange={(e) => setFamilyForm({...familyForm, nomineeRelation: e.target.value})} className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl font-medium focus:ring-2 focus:ring-slate-900" /></div>
                  </div>
                </div>

                <div className="pt-8 border-t border-slate-100">
                  <button type="submit" className="w-full md:w-auto px-10 py-4 bg-slate-900 hover:bg-slate-800 text-white font-bold rounded-xl shadow-lg transition-all hover:-translate-y-0.5">Save Profile Information</button>
                </div>
              </div>
            </form>
          </div>
        </div>
      </div>
    );
  };

  // ---------------------------------------------------------
  // 4. KYC VERIFICATION TAB 
  // ---------------------------------------------------------
  const KycTab = () => {
    const [kycData, setKycData] = useState(null);
    const [isLoading, setIsLoading] = useState(true);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [statusMsg, setStatusMsg] = useState({ type: "", msg: "" });
    
    const [form, setForm] = useState({ pan_number: "", aadhar_number: "", bank_name: "", bank_account_no: "", bank_ifsc: "" });
    const [files, setFiles] = useState({ pan: null, aadhar_front: null, aadhar_back: null, bank_proof: null, photo: null, signature: null });

    const indianBanks = [
      "State Bank of India (SBI)", "HDFC Bank", "ICICI Bank", "Punjab National Bank (PNB)",
      "Axis Bank", "Canara Bank", "Bank of Baroda", "Union Bank of India",
      "Bank of India", "Indian Bank", "Central Bank of India", "Kotak Mahindra Bank", 
      "IndusInd Bank", "Yes Bank", "IDFC First Bank", "Other"
    ];

    useEffect(() => {
      const loadKyc = async () => {
        setIsLoading(true);
        const res = await fetchKycData();
        if (res.success && res.data) {
          setKycData(res.data);
          setForm({
            pan_number: res.data.pan_number || "", aadhar_number: res.data.aadhar_number || "",
            bank_name: res.data.bank_name || "", bank_account_no: res.data.bank_account_no || "", bank_ifsc: res.data.bank_ifsc || ""
          });
        }
        setIsLoading(false);
      };
      loadKyc();
    }, []);

    const handleFileChange = (e, key) => { setFiles({...files, [key]: e.target.files[0]}); };

    const handleSubmit = async (e) => {
      e.preventDefault(); setIsSubmitting(true); setStatusMsg({ type: "", msg: "" });
      const res = await submitKycData(form);
      if (res.success) {
        setStatusMsg({ type: "success", msg: "KYC Documents & Details submitted successfully." });
        const updated = await fetchKycData();
        if (updated.success) setKycData(updated.data);
      } else { setStatusMsg({ type: "error", msg: res.message }); }
      setIsSubmitting(false);
    };

    const isLocked = kycData?.kyc_status === 'pending' || kycData?.kyc_status === 'approved';

    const FileUploadBox = ({ label, keyName }) => (
      <div className={`relative border-2 border-dashed rounded-2xl p-6 flex flex-col items-center justify-center text-center transition-all ${files[keyName] ? 'border-emerald-500 bg-emerald-50' : 'border-slate-300 hover:border-slate-400 bg-slate-50 hover:bg-slate-100'} ${isLocked ? 'opacity-50 pointer-events-none' : 'cursor-pointer'}`}>
        <input type="file" disabled={isLocked} onChange={(e) => handleFileChange(e, keyName)} accept="image/*,.pdf" className="absolute inset-0 w-full h-full opacity-0 cursor-pointer disabled:cursor-not-allowed" />
        {files[keyName] ? (
          <><CheckCircle2 className="h-8 w-8 text-emerald-500 mb-2" /><p className="text-sm font-bold text-emerald-800 break-all">{files[keyName].name}</p></>
        ) : (
          <><UploadCloud className="h-8 w-8 text-slate-400 mb-2" /><p className="text-sm font-bold text-slate-700">{label}</p><p className="text-xs text-slate-500 mt-1">Click or drag file</p></>
        )}
      </div>
    );

    return (
      <div className="max-w-6xl mx-auto space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
        <div className="mb-8">
          <h2 className="text-3xl font-black text-slate-900 tracking-tight">KYC Verification</h2>
          <p className="text-slate-500 font-medium mt-1">Upload your identity and banking proofs to unlock platform payouts.</p>
        </div>

        {isLoading ? <div className="flex justify-center py-20"><Loader2 className="h-10 w-10 animate-spin text-emerald-500" /></div> : (
          <div className="bg-white rounded-[2rem] shadow-[0_8px_30px_rgb(0,0,0,0.04)] border border-slate-100 overflow-hidden">
            
            <div className={`p-8 border-b flex items-center ${kycData?.kyc_status === 'approved' ? 'bg-emerald-50 border-emerald-100 text-emerald-800' : kycData?.kyc_status === 'pending' ? 'bg-amber-50 border-amber-100 text-amber-800' : kycData?.kyc_status === 'rejected' ? 'bg-red-50 border-red-100 text-red-800' : 'bg-slate-50 border-slate-100 text-slate-800'}`}>
              <ShieldCheck className="h-10 w-10 mr-5 shrink-0" />
              <div>
                <h4 className="font-bold uppercase tracking-wider text-xs mb-1 opacity-80">Verification Status</h4>
                <p className="font-black text-2xl capitalize tracking-tight">{kycData?.kyc_status || 'Unverified'}</p>
                {kycData?.kyc_status === 'rejected' && <p className="text-sm mt-2 font-bold text-red-600 bg-red-100/50 inline-block px-3 py-1 rounded-md border border-red-200">Reason: {kycData.kyc_rejection_reason}</p>}
              </div>
            </div>

            <div className="p-8 md:p-10">
              {statusMsg.msg && <div className={`p-5 rounded-2xl mb-8 flex items-center shadow-sm ${statusMsg.type === 'error' ? 'bg-red-50 text-red-700 border border-red-200' : 'bg-emerald-50 text-emerald-700 border border-emerald-200'}`}><AlertCircle className="h-6 w-6 mr-4 shrink-0" /><p className="font-bold text-sm">{statusMsg.msg}</p></div>}

              <form onSubmit={handleSubmit} className="space-y-12">
                <div className="space-y-6">
                  <h3 className="text-xl font-black text-slate-900 border-b border-slate-100 pb-3 flex items-center"><UserCircle className="mr-3 h-6 w-6 text-indigo-500"/> Identity Documents</h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div><label className="block text-sm font-bold text-slate-700 mb-2">PAN Card Number</label><input type="text" required disabled={isLocked} value={form.pan_number} onChange={(e) => setForm({...form, pan_number: e.target.value.toUpperCase()})} className="w-full px-5 py-4 bg-slate-50 border border-slate-200 rounded-2xl font-medium focus:ring-2 focus:ring-indigo-500 transition-all" placeholder="ABCDE1234F" /></div>
                    <div><label className="block text-sm font-bold text-slate-700 mb-2">Aadhar Card Number</label><input type="text" required disabled={isLocked} value={form.aadhar_number} onChange={(e) => setForm({...form, aadhar_number: e.target.value.replace(/\D/g, '')})} maxLength="12" className="w-full px-5 py-4 bg-slate-50 border border-slate-200 rounded-2xl font-medium focus:ring-2 focus:ring-indigo-500 transition-all" placeholder="XXXX XXXX XXXX" /></div>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                    <FileUploadBox label="Upload Self Photo" keyName="photo" />
                    <FileUploadBox label="PAN Card Image" keyName="pan" />
                    <FileUploadBox label="Aadhar Front" keyName="aadhar_front" />
                    <FileUploadBox label="Aadhar Back" keyName="aadhar_back" />
                  </div>
                </div>

                <div className="space-y-6">
                  <h3 className="text-xl font-black text-slate-900 border-b border-slate-100 pb-3 flex items-center"><Wallet className="mr-3 h-6 w-6 text-emerald-500"/> Payout Bank Details</h3>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                    <div>
                      <label className="block text-sm font-bold text-slate-700 mb-2">Bank Name</label>
                      <select required disabled={isLocked} value={form.bank_name} onChange={(e) => setForm({...form, bank_name: e.target.value})} className="w-full px-5 py-4 bg-slate-50 border border-slate-200 rounded-2xl font-medium focus:ring-2 focus:ring-emerald-500 transition-all">
                        <option value="" disabled>Select your bank</option>
                        {indianBanks.map(bank => <option key={bank} value={bank}>{bank}</option>)}
                      </select>
                    </div>
                    <div><label className="block text-sm font-bold text-slate-700 mb-2">Account Number</label><input type="text" required disabled={isLocked} value={form.bank_account_no} onChange={(e) => setForm({...form, bank_account_no: e.target.value.replace(/\D/g, '')})} className="w-full px-5 py-4 bg-slate-50 border border-slate-200 rounded-2xl font-medium focus:ring-2 focus:ring-emerald-500 transition-all" placeholder="Account Number" /></div>
                    <div><label className="block text-sm font-bold text-slate-700 mb-2">IFSC Code</label><input type="text" required disabled={isLocked} value={form.bank_ifsc} onChange={(e) => setForm({...form, bank_ifsc: e.target.value.toUpperCase()})} className="w-full px-5 py-4 bg-slate-50 border border-slate-200 rounded-2xl font-medium focus:ring-2 focus:ring-emerald-500 transition-all" placeholder="HDFC0001234" /></div>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <FileUploadBox label="Upload Bank Passbook / Cheque" keyName="bank_proof" />
                    <FileUploadBox label="Upload Digital Signature" keyName="signature" />
                  </div>
                </div>

                {!isLocked && (
                  <button type="submit" disabled={isSubmitting} className="w-full py-4 px-6 bg-slate-900 hover:bg-slate-800 text-white font-black text-lg rounded-2xl shadow-xl transition-all flex items-center justify-center hover:-translate-y-1">
                    {isSubmitting ? <Loader2 className="h-6 w-6 animate-spin" /> : "Submit Documents for Verification"}
                  </button>
                )}
              </form>
            </div>
          </div>
        )}
      </div>
    );
  };

  // ---------------------------------------------------------
  // 5. WALLET TAB
  // ---------------------------------------------------------
  const WalletTab = () => {
    const [balance, setBalance] = useState(0);
    const [transactions, setTransactions] = useState([]);
    const [isLoading, setIsLoading] = useState(true);
    const [isWithdrawModalOpen, setIsWithdrawModalOpen] = useState(false);
    const [withdrawAmount, setWithdrawAmount] = useState("");
    const [payoutMethod, setPayoutMethod] = useState("upi");
    const [payoutDetails, setPayoutDetails] = useState({ upiId: "", upiMobile: "", bankAccount: "", bankIfsc: "" });
    const [withdrawStatus, setWithdrawStatus] = useState({ type: "", msg: "" });
    const [isWithdrawing, setIsWithdrawing] = useState(false);
    const [isTransferModalOpen, setIsTransferModalOpen] = useState(false);
    const [transferReceiver, setTransferReceiver] = useState("");
    const [transferAmount, setTransferAmount] = useState("");
    const [transferStatus, setTransferStatus] = useState({ type: "", msg: "" });
    const [isTransferring, setIsTransferring] = useState(false);
    const [selectedTx, setSelectedTx] = useState(null);

    const loadWallet = async () => {
      setIsLoading(true);
      const res = await fetchWalletData(); 
      if (res.success) { setBalance(res.balance); setTransactions(res.history); }
      setIsLoading(false);
    };

    useEffect(() => { loadWallet(); }, []);

    const handleWithdraw = async (e) => {
        e.preventDefault(); setWithdrawStatus({ type: "", msg: "" });
        const amount = parseFloat(withdrawAmount);
        if (!amount || amount <= 0) return setWithdrawStatus({ type: "error", msg: "Enter a valid amount." });
        if (amount > balance) return setWithdrawStatus({ type: "error", msg: "Insufficient balance." });
        if (payoutMethod === "upi" && (!payoutDetails.upiId || !payoutDetails.upiMobile)) return setWithdrawStatus({ type: "error", msg: "Please fill in all UPI details." });
        if (payoutMethod === "bank" && (!payoutDetails.bankAccount || !payoutDetails.bankIfsc)) return setWithdrawStatus({ type: "error", msg: "Please fill in all Bank details." });
        setIsWithdrawing(true);
        const res = await submitWithdrawal(amount, payoutMethod, payoutDetails);
        if (res.success) {
            setWithdrawStatus({ type: "success", msg: res.message }); setWithdrawAmount("");
            await loadWallet(); setTimeout(() => { setIsWithdrawModalOpen(false); setWithdrawStatus({ type: "", msg: "" }); }, 2000);
        } else { setWithdrawStatus({ type: "error", msg: res.message }); }
        setIsWithdrawing(false);
    };

    const handleTransfer = async (e) => {
        e.preventDefault(); setTransferStatus({ type: "", msg: "" });
        const amount = parseFloat(transferAmount);
        if (!transferReceiver) return setTransferStatus({ type: "error", msg: "Enter a valid User ID or Email." });
        if (!amount || amount <= 0) return setTransferStatus({ type: "error", msg: "Enter a valid amount." });
        if (amount > balance) return setTransferStatus({ type: "error", msg: "Insufficient balance." });
        setIsTransferring(true);
        const res = await submitP2PTransfer(transferReceiver, amount);
        if (res.success) {
            setTransferStatus({ type: "success", msg: res.message }); setTransferAmount(""); setTransferReceiver("");
            await loadWallet(); setTimeout(() => { setIsTransferModalOpen(false); setTransferStatus({ type: "", msg: "" }); }, 2000);
        } else { setTransferStatus({ type: "error", msg: res.message }); }
        setIsTransferring(false);
    };

    return (
        <div className="max-w-6xl mx-auto space-y-8 relative animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="mb-8">
              <h2 className="text-3xl font-black text-slate-900 tracking-tight">Wallet & Earnings</h2>
              <p className="text-slate-500 font-medium mt-1">Manage commissions, request payouts, and transfer funds instantly.</p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div className="md:col-span-2 bg-gradient-to-br from-emerald-600 to-teal-900 rounded-[2rem] shadow-xl border border-emerald-800 p-8 text-white relative overflow-hidden group">
                <div className="absolute inset-0 bg-[url('https://www.transparenttextures.com/patterns/cubes.png')] opacity-20 mix-blend-overlay"></div>
                <div className="relative z-10 flex flex-col h-full justify-between">
                  <div>
                    <p className="text-emerald-100 font-bold text-sm mb-2 uppercase tracking-widest flex items-center"><Wallet className="h-4 w-4 mr-2"/> Available Balance</p>
                    <h3 className="text-5xl font-black tracking-tighter mb-8 drop-shadow-md">₹{isLoading ? "..." : parseFloat(balance).toLocaleString('en-IN', {minimumFractionDigits: 2})}</h3>
                  </div>
                  <div className="flex flex-wrap gap-4">
                    <button onClick={() => setIsWithdrawModalOpen(true)} className="px-6 py-3 bg-white text-emerald-700 hover:bg-slate-50 text-sm font-black rounded-xl shadow-lg hover:shadow-xl transition-all flex items-center hover:-translate-y-1">
                      <TrendingUp className="h-5 w-5 mr-2" /> Request Payout
                    </button>
                    <button onClick={() => setIsTransferModalOpen(true)} className="px-6 py-3 bg-black/20 hover:bg-black/30 text-white border border-white/20 text-sm font-bold rounded-xl shadow-lg backdrop-blur-md transition-all flex items-center hover:-translate-y-1">
                      <ArrowRightLeft className="h-5 w-5 mr-2" /> P2P Transfer
                    </button>
                  </div>
                </div>
                <Wallet className="absolute -bottom-10 -right-10 h-64 w-64 text-white/10 rotate-12 group-hover:scale-110 transition-transform duration-700" />
              </div>

              <div className="bg-white rounded-[2rem] shadow-[0_8px_30px_rgb(0,0,0,0.04)] border border-slate-100 p-8 flex flex-col justify-center items-center text-center hover:shadow-lg transition-shadow">
                <div className="p-4 bg-blue-50 text-blue-600 rounded-2xl mb-4"><ArrowRightLeft className="h-8 w-8" /></div>
                <h4 className="text-xl font-black text-slate-900">Zero Fee Transfers</h4>
                <p className="text-sm font-medium text-slate-500 mt-3">Send wallet funds instantly to any registered network member using their ID.</p>
              </div>
            </div>

            <div className="bg-white rounded-[2rem] shadow-[0_8px_30px_rgb(0,0,0,0.04)] border border-slate-100 overflow-hidden mt-8">
              <div className="px-8 py-6 border-b border-slate-100 bg-slate-50/50">
                <h3 className="text-xl font-black text-slate-900">Transaction Ledger</h3>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="bg-slate-50 text-slate-500 font-bold border-b border-slate-200 uppercase tracking-wider text-xs">
                    <tr><th className="px-8 py-4">Date</th><th className="px-8 py-4">Description</th><th className="px-8 py-4">Type</th><th className="px-8 py-4 text-right">Amount</th></tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {isLoading ? <tr><td colSpan="4" className="px-8 py-12 text-center text-slate-400"><Loader2 className="h-8 w-8 animate-spin mx-auto mb-3 text-emerald-500" /> Syncing ledger...</td></tr>
                    : transactions.length === 0 ? <tr><td colSpan="4" className="px-8 py-16 text-center text-slate-500"><Receipt className="h-12 w-12 text-slate-200 mx-auto mb-3"/>No transactions found.</td></tr>
                    : transactions.map((tx, idx) => (
                      <tr key={idx} onClick={() => setSelectedTx(tx)} className="hover:bg-slate-50 transition-colors cursor-pointer group">
                        <td className="px-8 py-5 text-slate-600 font-medium whitespace-nowrap">{new Date(tx.created_at).toLocaleDateString('en-IN')}</td>
                        <td className="px-8 py-5 text-slate-900 font-bold group-hover:text-emerald-600 transition-colors flex items-center">
                          {tx.description || tx.reference} 
                          {tx.description?.toLowerCase().includes("package") && <ShoppingBag className="h-4 w-4 ml-2 text-slate-300" />}
                        </td>
                        <td className="px-8 py-5"><span className={`px-3 py-1.5 text-xs font-bold rounded-lg ${tx.transaction_type.includes('credit') || tx.transaction_type.includes('commission') || tx.transaction_type.includes('in') ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800'}`}>{tx.transaction_type.replace(/_/g, ' ').toUpperCase()}</span></td>
                        <td className={`px-8 py-5 text-right text-lg font-black whitespace-nowrap ${tx.amount > 0 ? "text-emerald-600" : "text-slate-900"}`}>{tx.amount > 0 ? "+" : ""}₹{parseFloat(Math.abs(tx.amount)).toFixed(2)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* WITHDRAW MODAL */}
            {isWithdrawModalOpen && (
              <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-md animate-in fade-in">
                <div className="bg-white rounded-3xl shadow-2xl w-full max-w-md overflow-hidden animate-in zoom-in-95 max-h-[90vh] flex flex-col">
                  <div className="px-6 py-5 border-b border-slate-100 flex justify-between items-center bg-slate-50 shrink-0">
                    <h3 className="text-xl font-black text-slate-900">Request Payout</h3>
                    <button onClick={() => setIsWithdrawModalOpen(false)} className="text-slate-400 hover:text-slate-900 transition-colors bg-white p-2 rounded-full shadow-sm"><X className="h-5 w-5" /></button>
                  </div>
                  <div className="p-6 overflow-y-auto space-y-6">
                    {withdrawStatus.msg && <div className={`p-4 rounded-xl flex items-start ${withdrawStatus.type === 'error' ? 'bg-red-50 border border-red-200 text-red-700' : 'bg-emerald-50 border border-emerald-200 text-emerald-700'}`}><AlertCircle className="h-5 w-5 mr-3 shrink-0 mt-0.5" /><p className="text-sm font-bold">{withdrawStatus.msg}</p></div>}
                    <div className="bg-slate-50 p-5 rounded-2xl border border-slate-200 flex justify-between items-center">
                      <span className="text-sm font-bold text-slate-500 uppercase tracking-widest">Available Balance</span><span className="text-2xl font-black text-emerald-600">₹{parseFloat(balance).toFixed(2)}</span>
                    </div>
                    <form onSubmit={handleWithdraw} className="space-y-6">
                      <div>
                        <label className="block text-sm font-bold text-slate-700 mb-2">Withdrawal Amount (₹)</label>
                        <input type="number" min="1" step="0.01" value={withdrawAmount} onChange={(e) => setWithdrawAmount(e.target.value)} placeholder="e.g. 1500" className="w-full px-5 py-4 bg-white border border-slate-300 rounded-2xl text-slate-900 text-xl font-black focus:ring-2 focus:ring-emerald-500 transition-all shadow-sm" />
                      </div>
                      <div>
                        <label className="block text-sm font-bold text-slate-700 mb-3">Select Payout Method</label>
                        <div className="flex gap-3">
                          <button type="button" onClick={() => setPayoutMethod('upi')} className={`flex-1 py-3 rounded-xl border-2 text-sm font-black transition-all ${payoutMethod === 'upi' ? 'bg-emerald-50 border-emerald-500 text-emerald-700' : 'bg-white border-slate-200 text-slate-500 hover:bg-slate-50'}`}>UPI Transfer</button>
                          <button type="button" onClick={() => setPayoutMethod('bank')} className={`flex-1 py-3 rounded-xl border-2 text-sm font-black transition-all ${payoutMethod === 'bank' ? 'bg-emerald-50 border-emerald-500 text-emerald-700' : 'bg-white border-slate-200 text-slate-500 hover:bg-slate-50'}`}>Bank Transfer</button>
                        </div>
                      </div>
                      {payoutMethod === 'upi' ? (
                        <div className="space-y-4 bg-slate-50 p-5 rounded-2xl border border-slate-100">
                          <div><label className="block text-xs font-bold text-slate-600 mb-2 uppercase tracking-wider">UPI ID</label><input type="text" placeholder="example@upi" value={payoutDetails.upiId} onChange={(e) => setPayoutDetails({...payoutDetails, upiId: e.target.value})} className="w-full px-4 py-3 border border-slate-200 rounded-xl text-sm font-medium focus:ring-2 focus:ring-emerald-500" /></div>
                          <div><label className="block text-xs font-bold text-slate-600 mb-2 uppercase tracking-wider">UPI Linked Mobile Number</label><input type="text" placeholder="9876543210" value={payoutDetails.upiMobile} onChange={(e) => setPayoutDetails({...payoutDetails, upiMobile: e.target.value})} className="w-full px-4 py-3 border border-slate-200 rounded-xl text-sm font-medium focus:ring-2 focus:ring-emerald-500" /></div>
                        </div>
                      ) : (
                        <div className="space-y-4 bg-slate-50 p-5 rounded-2xl border border-slate-100">
                          <div><label className="block text-xs font-bold text-slate-600 mb-2 uppercase tracking-wider">Bank Account Number</label><input type="text" placeholder="Account Number" value={payoutDetails.bankAccount} onChange={(e) => setPayoutDetails({...payoutDetails, bankAccount: e.target.value})} className="w-full px-4 py-3 border border-slate-200 rounded-xl text-sm font-medium focus:ring-2 focus:ring-emerald-500" /></div>
                          <div><label className="block text-xs font-bold text-slate-600 mb-2 uppercase tracking-wider">IFSC Code</label><input type="text" placeholder="IFSC Code" value={payoutDetails.bankIfsc} onChange={(e) => setPayoutDetails({...payoutDetails, bankIfsc: e.target.value})} className="w-full px-4 py-3 border border-slate-200 rounded-xl text-sm font-medium focus:ring-2 focus:ring-emerald-500" /></div>
                        </div>
                      )}
                      <button type="submit" disabled={isWithdrawing || !withdrawAmount} className="w-full py-4 px-4 bg-emerald-600 hover:bg-emerald-700 text-white font-black text-lg rounded-2xl shadow-lg transition-all disabled:opacity-50 flex items-center justify-center mt-6">
                        {isWithdrawing ? <Loader2 className="h-6 w-6 animate-spin" /> : "Submit Withdrawal Request"}
                      </button>
                    </form>
                  </div>
                </div>
              </div>
            )}

            {/* TRANSFER MODAL */}
            {isTransferModalOpen && (
              <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-md animate-in fade-in">
                <div className="bg-white rounded-3xl shadow-2xl w-full max-w-md overflow-hidden animate-in zoom-in-95">
                  <div className="px-6 py-5 border-b border-slate-100 flex justify-between items-center bg-slate-50"><h3 className="text-xl font-black text-slate-900">Transfer Funds</h3><button onClick={() => setIsTransferModalOpen(false)} className="text-slate-400 hover:text-slate-900 transition-colors bg-white p-2 rounded-full shadow-sm"><X className="h-5 w-5" /></button></div>
                  <div className="p-6 space-y-6">
                    {transferStatus.msg && <div className={`p-4 rounded-xl flex items-start ${transferStatus.type === 'error' ? 'bg-red-50 border border-red-200 text-red-700' : 'bg-emerald-50 border border-emerald-200 text-emerald-700'}`}><AlertCircle className="h-5 w-5 mr-3 shrink-0 mt-0.5" /><p className="text-sm font-bold">{transferStatus.msg}</p></div>}
                    <div className="bg-slate-50 p-5 rounded-2xl border border-slate-200 flex justify-between items-center"><span className="text-sm font-bold text-slate-500 uppercase tracking-widest">Available Balance</span><span className="text-2xl font-black text-slate-900">₹{parseFloat(balance).toFixed(2)}</span></div>
                    <form onSubmit={handleTransfer} className="space-y-4">
                      <div><label className="block text-sm font-bold text-slate-700 mb-2">Receiver User ID or Email</label><input type="text" value={transferReceiver} onChange={(e) => setTransferReceiver(e.target.value)} placeholder="e.g. 45 or john@email.com" className="w-full px-5 py-4 bg-white border border-slate-300 rounded-2xl text-slate-900 font-medium focus:ring-2 focus:ring-slate-900 shadow-sm transition-all" /></div>
                      <div><label className="block text-sm font-bold text-slate-700 mb-2">Transfer Amount (₹)</label><input type="number" min="1" step="0.01" value={transferAmount} onChange={(e) => setTransferAmount(e.target.value)} placeholder="e.g. 500" className="w-full px-5 py-4 bg-white border border-slate-300 rounded-2xl text-slate-900 text-xl font-black focus:ring-2 focus:ring-slate-900 shadow-sm transition-all" /></div>
                      <button type="submit" disabled={isTransferring || !transferAmount || !transferReceiver} className="w-full py-4 px-4 bg-slate-900 hover:bg-slate-800 text-white font-black text-lg rounded-2xl shadow-lg transition-all disabled:opacity-50 flex items-center justify-center mt-6">
                        {isTransferring ? <Loader2 className="h-6 w-6 animate-spin" /> : "Send Funds Instantly"}
                      </button>
                    </form>
                  </div>
                </div>
              </div>
            )}

            {selectedTx && (
              <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-in fade-in">
                <div className="bg-white rounded-2xl shadow-2xl w-full max-w-sm overflow-hidden animate-in zoom-in-95">
                  <div className="px-6 py-4 border-b border-slate-100 flex justify-between items-center bg-slate-50">
                    <h3 className="text-lg font-bold text-slate-900 flex items-center"><Receipt className="h-5 w-5 mr-2 text-slate-400" /> Transaction Receipt</h3>
                    <button onClick={() => setSelectedTx(null)} className="text-slate-400 hover:text-slate-600 transition-colors"><X className="h-5 w-5" /></button>
                  </div>
                  <div className="p-6">
                    <div className="text-center mb-6">
                      <div className={`inline-flex items-center justify-center h-16 w-16 rounded-full mb-4 ${selectedTx.amount > 0 ? 'bg-emerald-100 text-emerald-600' : 'bg-amber-100 text-amber-600'}`}>
                        {selectedTx.amount > 0 ? <TrendingUp className="h-8 w-8" /> : <ArrowRightLeft className="h-8 w-8" />}
                      </div>
                      <h4 className="text-3xl font-black text-slate-900">
                        {selectedTx.amount > 0 ? "+" : ""}₹{parseFloat(Math.abs(selectedTx.amount)).toFixed(2)}
                      </h4>
                      <p className={`text-sm font-bold mt-1 ${selectedTx.amount > 0 ? 'text-emerald-600' : 'text-amber-600'}`}>
                        {selectedTx.transaction_type.replace(/_/g, ' ').toUpperCase()}
                      </p>
                    </div>

                    <div className="bg-slate-50 rounded-xl border border-slate-100 p-4 space-y-3">
                      <div className="flex justify-between items-start">
                        <span className="text-sm font-medium text-slate-500">Date & Time</span>
                        <span className="text-sm font-bold text-slate-900 text-right">{new Date(selectedTx.created_at).toLocaleString()}</span>
                      </div>
                      <hr className="border-slate-200" />
                      <div className="flex justify-between items-start">
                        <span className="text-sm font-medium text-slate-500">Details</span>
                        <span className="text-sm font-bold text-slate-900 text-right max-w-[60%]">{selectedTx.description || 'System Transfer'}</span>
                      </div>
                      <hr className="border-slate-200" />
                      <div className="flex justify-between items-start">
                        <span className="text-sm font-medium text-slate-500">Reference ID</span>
                        <span className="text-xs font-mono text-slate-400 bg-white border border-slate-200 px-2 py-1 rounded select-all">{selectedTx.reference || `TXN-${selectedTx.id}`}</span>
                      </div>
                    </div>

                    {selectedTx.description?.toLowerCase().includes("package") && (
                      <div className="mt-4 bg-indigo-50 border border-indigo-100 rounded-xl p-4 flex items-start">
                        <Info className="h-5 w-5 text-indigo-500 mr-3 shrink-0 mt-0.5" />
                        <p className="text-xs font-medium text-indigo-800">
                          This transaction is linked to a product purchase in your catalog. You can view the full GST invoice for this item in the <strong>"My Orders & Invoices"</strong> tab.
                        </p>
                      </div>
                    )}
                    
                    <button onClick={() => setSelectedTx(null)} className="mt-6 w-full py-3 bg-slate-900 hover:bg-slate-800 text-white font-bold rounded-lg shadow-md transition-all">
                      Close Receipt
                    </button>
                  </div>
                </div>
              </div>
            )}
        </div>
    );
  };

  // ---------------------------------------------------------
  // 6. NETWORK TAB (DUAL-VIEW ORG CHART & DIRECTORY LIST)
  // ---------------------------------------------------------
  const NetworkTab = () => {
    const [networkStats, setNetworkStats] = useState({ total: 0, direct: [] });
    const [fullTreeData, setFullTreeData] = useState(null);
    const [currentViewNode, setCurrentViewNode] = useState(null);
    const [uplineData, setUplineData] = useState([]);
    const [flatTeam, setFlatTeam] = useState([]);
    const [isLoading, setIsLoading] = useState(true);
    const [viewMode, setViewMode] = useState("tree"); 
    const treeContainerRef = useRef(null);

    useEffect(() => {
      const loadNetwork = async () => {
        setIsLoading(true);
        try {
          const [networkRes, uplineRes] = await Promise.all([
            fetchNetworkData(),
            fetchUplineData()
          ]);

          if (networkRes.success) {
            setNetworkStats({ total: networkRes.totalCount || 0, direct: networkRes.directTeam || [] });
            
            // Defensively handle backend returning an Array instead of an Object
            let rawTree = networkRes.tree;
            if (Array.isArray(rawTree) && rawTree.length > 0) {
                rawTree = rawTree[0];
            } else if (Array.isArray(rawTree) && rawTree.length === 0) {
                rawTree = null;
            }
            
            if (rawTree && typeof rawTree === 'object' && Object.keys(rawTree).length > 0) {
              const mapNode = (node, depth = 1) => {
                if (!node) return null;
                const id = node.user_id || node.id || 'N/A';
                return {
                  user_id: id,
                  full_name: node.full_name || node.name || `User #${id}`,
                  email: node.email || 'N/A',
                  phone: node.phone || 'N/A',
                  is_active: node.is_active === true || node.is_active === 1 || node.is_active === 'Active',
                  level: node.level || depth,
                  joinDate: node.created_at || node.joinDate || new Date().toISOString(),
                  children: Array.isArray(node.children) ? node.children.map(child => mapNode(child, depth + 1)).filter(Boolean) : []
                };
              };

              const processedTree = mapNode(rawTree);
              setFullTreeData(processedTree);
              setCurrentViewNode(processedTree);

              const flattenTree = (node) => {
                let list = [];
                if (!node) return list;
                if (node.user_id && node.user_id !== 'N/A') { 
                   list.push(node);
                }
                if (node.children && Array.isArray(node.children)) {
                   node.children.forEach(child => { list = list.concat(flattenTree(child)); });
                }
                return list;
              };
              
              const flat = flattenTree(processedTree).filter(n => n.user_id !== processedTree.user_id);
              setFlatTeam(flat);
            }
          }

          if (uplineRes.success && Array.isArray(uplineRes.data)) {
            const safeUpline = uplineRes.data.map(u => ({
              user_id: u.user_id || u.id || 'N/A',
              full_name: u.full_name || `User #${u.user_id || u.id || 'N/A'}`,
              email: u.email || 'N/A',
              phone: u.phone || 'N/A',
              level: u.level || 1
            }));
            setUplineData(safeUpline);
          }
        } catch (error) {
          console.error("Failed to compile network view", error);
        }
        setIsLoading(false);
      };
      loadNetwork();
    }, []);

    const handleDrillDown = (node) => {
      setCurrentViewNode(node);
      setViewMode("tree");
      setTimeout(() => treeContainerRef.current?.scrollIntoView({ behavior: 'smooth' }), 100);
    };

    const handleResetTree = () => {
      setCurrentViewNode(fullTreeData);
    };

    const OrgChartNode = ({ node, isRoot = false }) => {
      const [expanded, setExpanded] = useState(true);
      if (!node) return null;
      
      const hasChildren = node.children && node.children.length > 0;

      return (
        <div className="flex flex-col items-center">
          <div className={`relative z-10 w-72 bg-white rounded-2xl shadow-md border-2 transition-all duration-300 ${isRoot ? 'border-indigo-500 shadow-indigo-100' : node.is_active ? 'border-emerald-500 hover:shadow-emerald-100' : 'border-slate-200'}`}>
            <div className={`p-4 border-b flex justify-between items-center ${isRoot ? 'bg-indigo-50' : node.is_active ? 'bg-emerald-50' : 'bg-slate-50'} rounded-t-2xl`}>
              <div className="flex items-center">
                <div className={`h-10 w-10 rounded-full flex items-center justify-center font-black text-white shadow-inner ${isRoot ? 'bg-indigo-500' : node.is_active ? 'bg-emerald-500' : 'bg-slate-400'}`}>
                  {node.full_name ? node.full_name.charAt(0).toUpperCase() : 'U'}
                </div>
                <div className="ml-3">
                  <h4 className="font-black text-slate-900 leading-tight truncate w-32" title={node.full_name}>{node.full_name}</h4>
                  <p className="text-xs font-bold text-slate-500 mt-0.5">ID: #{node.user_id}</p>
                </div>
              </div>
              <span className={`text-[10px] font-black uppercase tracking-wider px-2 py-1 rounded-md ${node.is_active ? 'bg-emerald-200 text-emerald-800' : 'bg-slate-200 text-slate-600'}`}>
                {node.is_active ? 'Active' : 'Inactive'}
              </span>
            </div>
            <div className="p-4 space-y-2 bg-white rounded-b-2xl">
              <div className="flex justify-between items-center text-xs">
                <span className="font-semibold text-slate-500">Rank / Lvl</span>
                <span className="font-black text-indigo-600">{isRoot ? 'Distributor' : `Level ${node.level}`}</span>
              </div>
              <div className="flex justify-between items-center text-xs">
                <span className="font-semibold text-slate-500">Phone</span>
                <span className="font-bold text-slate-800">{node.phone}</span>
              </div>
              <div className="flex justify-between items-center text-xs">
                <span className="font-semibold text-slate-500">Email</span>
                <span className="font-bold text-slate-800 truncate w-32 text-right" title={node.email}>{node.email}</span>
              </div>
              
              {!isRoot && hasChildren && (
                <div className="pt-3 mt-3 border-t border-slate-100 flex justify-between gap-2">
                   <button onClick={() => setExpanded(!expanded)} className="flex-1 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-bold rounded-lg transition-colors">
                     {expanded ? 'Collapse' : 'Expand'}
                   </button>
                   <button onClick={() => handleDrillDown(node)} className="flex-1 py-1.5 bg-indigo-50 hover:bg-indigo-100 text-indigo-700 text-xs font-bold rounded-lg transition-colors">
                     Focus Team
                   </button>
                </div>
              )}
              {isRoot && fullTreeData && currentViewNode.user_id !== fullTreeData.user_id && (
                <div className="pt-3 mt-3 border-t border-slate-100">
                   <button onClick={handleResetTree} className="w-full py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold rounded-lg transition-colors">
                     Back to Top
                   </button>
                </div>
              )}
            </div>

            {hasChildren && (
              <div className="absolute -bottom-3 left-1/2 transform -translate-x-1/2 bg-white border-2 border-slate-200 rounded-full h-6 w-6 flex items-center justify-center text-slate-500 shadow-sm font-bold text-lg leading-none z-20 cursor-pointer hover:bg-slate-50" onClick={() => setExpanded(!expanded)}>
                {expanded ? '-' : '+'}
              </div>
            )}
          </div>

          {expanded && hasChildren && (
            <div className="flex flex-col items-center">
              <div className="w-0.5 h-6 bg-slate-300"></div>
              <div className="flex gap-6 relative pt-4">
                {node.children.length > 1 && (
                  <div className="absolute top-0 left-0 w-full h-0.5 bg-slate-300" style={{ width: `calc(100% - ${100 / node.children.length}%)`, left: `calc(${50 / node.children.length}%)` }}></div>
                )}
                {node.children.map((child, idx) => (
                  <div key={idx} className="flex flex-col items-center relative">
                    <div className="w-0.5 h-4 bg-slate-300 absolute top-0"></div>
                    <div className="pt-4">
                      <OrgChartNode node={child} isRoot={false} />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      );
    };

    return (
      <div className="max-w-7xl mx-auto space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
        <div className="mb-8 flex flex-col sm:flex-row justify-between sm:items-end gap-4">
          <div>
            <h2 className="text-3xl font-black text-slate-900 tracking-tight">My Network Matrix</h2>
            <p className="text-slate-500 font-medium mt-1">Track and manage your entire downline organization.</p>
          </div>
          <div className="flex bg-slate-200/50 p-1.5 rounded-xl border border-slate-200 self-start shadow-inner">
            <button onClick={() => setViewMode('tree')} className={`px-5 py-2.5 rounded-lg text-sm font-black transition-all ${viewMode === 'tree' ? 'bg-white text-indigo-600 shadow-md' : 'text-slate-500 hover:text-slate-800'}`}>Visual Chart</button>
            <button onClick={() => setViewMode('table')} className={`px-5 py-2.5 rounded-lg text-sm font-black transition-all ${viewMode === 'table' ? 'bg-white text-indigo-600 shadow-md' : 'text-slate-500 hover:text-slate-800'}`}>Directory List</button>
          </div>
        </div>
        
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="bg-gradient-to-br from-indigo-50 to-white rounded-[2rem] shadow-[0_8px_30px_rgb(0,0,0,0.04)] border border-indigo-100 p-6 relative overflow-hidden group hover:shadow-lg transition-all cursor-pointer" onClick={() => setViewMode('upline')}>
            <UserMinus className="absolute -right-4 -bottom-4 h-32 w-32 text-indigo-500/10 group-hover:scale-110 transition-transform" />
            <p className="text-xs font-bold text-indigo-500 uppercase tracking-widest mb-1">My Upline</p>
            <h3 className="text-2xl font-black text-slate-900">{uplineData.length > 0 ? uplineData[0].full_name : 'System Admin'}</h3>
            <p className="text-sm font-bold text-slate-500 mt-1 flex items-center">View full upline chain <ChevronRight className="h-4 w-4 ml-1"/></p>
          </div>

          <div onClick={() => setViewMode('tree')} className="bg-white rounded-[2rem] shadow-[0_8px_30px_rgb(0,0,0,0.04)] hover:shadow-xl transition-all border border-slate-100 p-6 flex items-center cursor-pointer hover:-translate-y-1 group">
            <div className="p-4 bg-blue-50 text-blue-600 rounded-2xl group-hover:bg-blue-600 group-hover:text-white transition-colors"><GitMerge className="h-8 w-8" /></div>
            <div className="ml-5"><p className="text-xs font-bold text-slate-400 uppercase tracking-widest">Total Network</p><h3 className="text-3xl font-black text-slate-900 mt-1">{isLoading ? "..." : networkStats.total} <span className="text-sm font-bold text-slate-500">Members</span></h3></div>
          </div>

          <div onClick={() => setViewMode('table')} className="bg-white rounded-[2rem] shadow-[0_8px_30px_rgb(0,0,0,0.04)] hover:shadow-xl transition-all border border-slate-100 p-6 flex items-center cursor-pointer hover:-translate-y-1 group">
            <div className="p-4 bg-emerald-50 text-emerald-600 rounded-2xl group-hover:bg-emerald-600 group-hover:text-white transition-colors"><UserPlus className="h-8 w-8" /></div>
            <div className="ml-5"><p className="text-xs font-bold text-slate-400 uppercase tracking-widest">Direct Referrals</p><h3 className="text-3xl font-black text-slate-900 mt-1">{isLoading ? "..." : networkStats.direct.length} <span className="text-sm font-bold text-slate-500">Directs</span></h3></div>
          </div>
        </div>

        {isLoading ? (
           <div className="h-96 flex flex-col items-center justify-center bg-white rounded-[2rem] border border-slate-100 shadow-sm mt-8"><Loader2 className="h-12 w-12 animate-spin text-indigo-500 mb-4" /><p className="text-slate-500 font-bold">Rendering matrix...</p></div>
        ) : viewMode === "tree" ? (
          <div ref={treeContainerRef} className="w-full bg-slate-100/50 rounded-[2rem] border-2 border-slate-200 overflow-x-auto mt-8 p-12 min-h-[600px] custom-scrollbar shadow-inner flex justify-center">
            {currentViewNode ? (
              <div className="min-w-max pb-20 pt-10">
                <OrgChartNode node={currentViewNode} isRoot={true} />
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center h-full text-slate-500 mt-20">
                <Users className="h-20 w-20 text-slate-300 mb-4" />
                <p className="font-bold text-lg text-slate-400">Your downline tree is empty.</p>
              </div>
            )}
          </div>
        ) : viewMode === "upline" ? (
          <div className="bg-white rounded-[2rem] shadow-[0_8px_30px_rgb(0,0,0,0.04)] border border-slate-100 overflow-hidden mt-8 animate-in fade-in">
             <div className="px-8 py-6 border-b border-slate-100 bg-indigo-50/50 flex items-center">
              <h3 className="text-xl font-black text-slate-900 flex items-center"><UserMinus className="h-6 w-6 mr-3 text-indigo-600"/> Upline Trace</h3>
            </div>
            <div className="p-8">
              {uplineData.length === 0 ? <p className="text-slate-500 font-bold text-center py-10">You are at the top of the organization.</p> : (
                <div className="space-y-4">
                  {uplineData.map((sponsor, idx) => (
                    <div key={idx} className="flex items-center bg-slate-50 p-4 rounded-2xl border border-slate-200 shadow-sm hover:shadow-md transition-shadow">
                      <div className="h-12 w-12 rounded-full bg-indigo-100 text-indigo-700 font-black flex items-center justify-center text-xl mr-5">{sponsor.full_name.charAt(0)}</div>
                      <div className="flex-1">
                        <h4 className="font-black text-slate-900 text-lg">{sponsor.full_name}</h4>
                        <div className="flex gap-4 text-xs font-bold text-slate-500 mt-1">
                           <span>ID: #{sponsor.user_id}</span>
                           <span>Email: {sponsor.email || 'N/A'}</span>
                        </div>
                      </div>
                      <div className="text-right">
                        <span className="block text-xs font-bold text-slate-400 uppercase tracking-wider mb-1">Level</span>
                        <span className="px-3 py-1 bg-white border border-slate-200 rounded-lg font-black text-slate-700">Upline {sponsor.level}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        ) : (
          <div className="bg-white rounded-[2rem] shadow-[0_8px_30px_rgb(0,0,0,0.04)] border border-slate-100 overflow-hidden mt-8 animate-in fade-in duration-300">
            <div className="px-8 py-6 border-b border-slate-100 bg-slate-50/50 flex items-center justify-between">
              <h3 className="text-xl font-black text-slate-900 flex items-center"><ListTree className="h-5 w-5 mr-3 text-emerald-500"/> Downline Directory</h3>
              <span className="bg-emerald-100 text-emerald-800 px-4 py-1.5 text-xs font-black rounded-xl uppercase tracking-wider">{flatTeam.length} Records</span>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="bg-slate-50 text-slate-400 font-bold border-b border-slate-100 uppercase tracking-wider text-xs">
                  <tr><th className="px-8 py-5">Member Details</th><th className="px-8 py-5 text-center">Generation Level</th><th className="px-8 py-5">Contact</th><th className="px-8 py-5 text-right">Action</th></tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {flatTeam.length === 0 ? <tr><td colSpan="4" className="px-8 py-16 text-center text-slate-500"><Users className="h-12 w-12 text-slate-200 mx-auto mb-3"/>Your network is currently empty.</td></tr>
                  : flatTeam.map((member, idx) => (
                    <tr key={idx} className="hover:bg-slate-50 transition-colors">
                      <td className="px-8 py-6">
                        <div className="flex items-center">
                          <div className="h-12 w-12 rounded-xl bg-gradient-to-br from-emerald-100 to-teal-100 flex items-center justify-center text-emerald-700 text-xl font-black mr-4 shadow-inner border border-emerald-200">
                            {member.full_name.charAt(0).toUpperCase()}
                          </div>
                          <div>
                            <span className="text-slate-900 font-black text-lg block leading-tight">{member.full_name}</span>
                            <span className="text-xs font-bold text-slate-400 mt-1">ID: #{member.user_id} • Joined {new Date(member.joinDate).toLocaleDateString('en-IN')}</span>
                          </div>
                        </div>
                      </td>
                      <td className="px-8 py-6 text-center">
                        <span className="px-5 py-2 bg-slate-100 border border-slate-200 text-slate-700 rounded-xl font-black text-sm shadow-sm block mb-2 w-max mx-auto">Level {member.level}</span>
                        <span className={`text-[10px] font-black uppercase tracking-wider px-2 py-1 rounded-md ${member.is_active ? 'bg-emerald-200 text-emerald-800' : 'bg-slate-200 text-slate-600'}`}>
                          {member.is_active ? 'Active' : 'Inactive'}
                        </span>
                      </td>
                      <td className="px-8 py-6">
                        <p className="font-bold text-slate-800 text-sm mb-1">{member.phone}</p>
                        <p className="text-xs font-semibold text-slate-500">{member.email}</p>
                      </td>
                      <td className="px-8 py-6 text-right">
                        <button onClick={() => handleDrillDown(member)} className="inline-flex items-center justify-center px-4 py-2 bg-indigo-50 text-indigo-700 hover:bg-indigo-600 hover:text-white rounded-xl transition-all text-sm font-bold shadow-sm border border-indigo-100">
                          <GitMerge className="h-4 w-4 mr-2" /> View Chart
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    );
  };

  // ---------------------------------------------------------
  // 7. PRODUCT CATALOG TAB
  // ---------------------------------------------------------
  const ProductCatalogTab = () => {
    const [packages, setPackages] = useState([]);
    const [compPlan, setCompPlan] = useState({ global: [], levels: [], bonuses: [] });
    const [isLoading, setIsLoading] = useState(true);
    const [buyStatus, setBuyStatus] = useState({ type: "", msg: "" });
    const [isPurchasing, setIsPurchasing] = useState(false);
    const [showSuccessModal, setShowSuccessModal] = useState(false);
    const [purchasedPlanDetails, setPurchasedPlanDetails] = useState(null);

    useEffect(() => {
      const loadData = async () => {
        setIsLoading(true);
        const [pkgRes, compRes] = await Promise.all([fetchPackages(), fetchCompensationPlan()]);
        if (pkgRes.success) setPackages(pkgRes.data);
        if (compRes.success && compRes.data) setCompPlan({ global: compRes.data.global || [], levels: compRes.data.levels || [], bonuses: compRes.data.bonuses || [] });
        setIsLoading(false);
      };
      loadData();
    }, []);

    const handleBuy = async (pkg) => {
      if (!window.confirm(`Are you sure you want to purchase the ${pkg.name} plan and join the network?`)) return;
      setIsPurchasing(true); setBuyStatus({ type: "", msg: "" });
      const res = await purchasePlan(pkg.id);
      if (res.success) { setPurchasedPlanDetails(pkg); setShowSuccessModal(true); } 
      else { setBuyStatus({ type: "error", msg: res.message }); }
      setIsPurchasing(false);
    };

    return (
      <div className="max-w-7xl mx-auto space-y-12 pb-12 relative animate-in fade-in slide-in-from-bottom-4 duration-500">
        {showSuccessModal && purchasedPlanDetails && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/70 backdrop-blur-md animate-in fade-in print:hidden">
            <div className="bg-white rounded-3xl shadow-2xl w-full max-w-md overflow-hidden animate-in zoom-in-95 text-center p-10">
              <div className="w-24 h-24 bg-emerald-100 rounded-full flex items-center justify-center mx-auto mb-6 shadow-inner border-4 border-white"><CheckCircle2 className="h-12 w-12 text-emerald-600" /></div>
              <h2 className="text-3xl font-black text-slate-900 mb-2 tracking-tight">Payment Successful!</h2>
              <p className="text-slate-500 font-medium mb-8">You activated <span className="font-bold text-slate-900">{purchasedPlanDetails.name}</span>.</p>
              <div className="bg-slate-50 p-4 rounded-xl border border-slate-100 mb-8 text-left">
                <div className="flex justify-between items-center mb-2"><span className="text-sm text-slate-500 font-medium">Amount Paid</span><span className="font-bold text-slate-900">₹{parseFloat(purchasedPlanDetails.price).toLocaleString('en-IN')}</span></div>
                <div className="flex justify-between items-center"><span className="text-sm text-slate-500 font-medium">Status</span><span className="text-xs font-bold bg-emerald-100 text-emerald-700 px-2.5 py-0.5 rounded-full">Activated</span></div>
              </div>
              <button onClick={() => { setShowSuccessModal(false); switchTab("My Orders & Invoices"); }} className="w-full py-4 bg-slate-900 hover:bg-slate-800 text-white font-black text-lg rounded-xl shadow-xl transition-all hover:-translate-y-1">
                View Tax Invoice
              </button>
            </div>
          </div>
        )}

        <div>
          <div className="flex flex-col sm:flex-row sm:justify-between sm:items-end mb-10 gap-4 print:hidden">
            <div><h2 className="text-3xl font-black text-slate-900 tracking-tight">Product Catalog</h2><p className="text-slate-500 font-medium mt-1">Choose an activation plan to unlock your earning potential.</p></div>
            <button onClick={() => window.print()} className="print:hidden flex items-center px-6 py-3 bg-white border border-slate-200 text-slate-700 hover:bg-slate-50 hover:text-indigo-600 rounded-xl shadow-sm font-bold text-sm transition-all">
              <Download className="h-4 w-4 mr-2" /> Download PDF Brochure
            </button>
          </div>
          {buyStatus.msg && <div className={`p-4 mb-6 rounded-xl border flex items-center print:hidden ${buyStatus.type === 'error' ? 'bg-red-50 border-red-200 text-red-700' : 'bg-emerald-50 border-emerald-200 text-emerald-700'}`}><AlertCircle className="h-5 w-5 mr-3 shrink-0" /><p className="font-semibold">{buyStatus.msg}</p></div>}
          
          {isLoading ? <div className="flex flex-col items-center justify-center h-64 print:hidden"><Loader2 className="h-10 w-10 text-emerald-500 animate-spin mb-4" /></div>
          : packages.length === 0 ? <div className="text-center p-10 bg-white rounded-3xl border border-slate-200 shadow-sm"><ShoppingBag className="h-12 w-12 text-slate-300 mx-auto mb-4" /><h3 className="text-xl font-bold text-slate-900">No Plans Available</h3></div>
          : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
              {packages.map((pkg) => (
                <div key={pkg.id} className={`bg-white rounded-[2rem] shadow-[0_8px_30px_rgb(0,0,0,0.04)] hover:shadow-2xl transition-all duration-300 hover:-translate-y-2 border ${pkg.is_popular ? 'border-emerald-500 shadow-emerald-100/50' : 'border-slate-100'} relative overflow-hidden flex flex-col group`}>
                  {pkg.is_popular && <div className="absolute top-0 inset-x-0 bg-gradient-to-r from-emerald-500 to-teal-500 text-white text-xs font-black uppercase tracking-widest text-center py-2 z-10 shadow-md">Most Popular</div>}
                  <div className="h-56 bg-slate-100 relative border-b border-slate-100 overflow-hidden">
                     {pkg.image_url ? <img src={pkg.image_url} alt={pkg.name} className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500" /> : <div className="flex items-center justify-center h-full text-slate-300"><ImageIcon className="h-20 w-20 opacity-20" /></div>}
                  </div>
                  <div className="p-8 pb-4">
                    <h3 className="text-3xl font-black text-slate-900 tracking-tight">{pkg.name}</h3>
                    <div className="mt-3 flex items-baseline text-5xl font-black text-emerald-600 drop-shadow-sm"><span className="text-2xl mr-1 font-bold text-emerald-400">₹</span>{parseFloat(pkg.price).toFixed(0)}</div>
                    <p className="text-slate-400 font-bold mt-2 text-xs uppercase tracking-wider">One-time activation fee</p>
                  </div>
                  <div className="p-8 pt-0 flex-1 flex flex-col">
                    <ul className="space-y-4 flex-1 mt-4">
                      <li className="flex items-start"><Zap className="h-6 w-6 text-amber-500 mr-3 shrink-0" /><span className="text-sm font-bold text-slate-700">Unlock {pkg.lucky_draw_coupons || 0} Lucky Draw Coupons</span></li>
                      <li className="flex items-start"><CheckCircle2 className="h-6 w-6 text-emerald-500 mr-3 shrink-0" /><span className="text-sm font-bold text-slate-700">Access to Multi-Level Commissions</span></li>
                    </ul>
                    <button onClick={() => handleBuy(pkg)} disabled={isPurchasing} className={`print:hidden mt-8 w-full py-4 px-4 rounded-xl font-black text-lg shadow-xl transition-all flex items-center justify-center hover:-translate-y-1 ${pkg.is_popular ? 'bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white' : 'bg-slate-900 hover:bg-slate-800 text-white'}`}>
                      {isPurchasing ? <Loader2 className="h-6 w-6 animate-spin" /> : "Purchase & Activate"}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <hr className="border-slate-200 print:hidden" />

        {!isLoading && (
          <div className="break-inside-avoid">
            <div className="mb-8"><h2 className="text-3xl font-black text-slate-900 tracking-tight">Platform Earning Rules</h2><p className="text-slate-500 font-medium mt-1">Your transparent, real-time compensation structure.</p></div>
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
              <div className="lg:col-span-1 space-y-6 break-inside-avoid">
                <div className="bg-white rounded-[2rem] shadow-[0_8px_30px_rgb(0,0,0,0.04)] border border-slate-100 overflow-hidden">
                  <div className="px-8 py-6 border-b border-slate-100 bg-slate-50/50 flex items-center"><Globe className="h-6 w-6 text-indigo-500 mr-3" /><h3 className="text-lg font-black text-slate-900">Global Commissions</h3></div>
                  <div className="p-8">
                    {compPlan.global.length === 0 ? <p className="text-sm font-medium text-slate-500">No global rules set.</p> : (
                      <ul className="space-y-5">
                        {compPlan.global.map((item, idx) => (
                          <li key={idx} className="flex justify-between items-center"><span className="text-sm font-bold text-slate-600 capitalize">{item.setting_key.replace(/_/g, ' ')}</span><span className="text-lg font-black text-indigo-600 bg-indigo-50 px-3 py-1 rounded-lg">{item.percentage_value}%</span></li>
                        ))}
                      </ul>
                    )}
                  </div>
                </div>
                <div className="bg-white rounded-[2rem] shadow-[0_8px_30px_rgb(0,0,0,0.04)] border border-slate-100 overflow-hidden break-inside-avoid">
                  <div className="px-8 py-6 border-b border-slate-100 bg-slate-50/50 flex items-center"><Target className="h-6 w-6 text-amber-500 mr-3" /><h3 className="text-lg font-black text-slate-900">Target Bonuses</h3></div>
                  <div className="p-0">
                    {compPlan.bonuses.length === 0 ? <p className="text-sm font-medium text-slate-500 p-8">No bonuses set.</p> : (
                      <table className="w-full text-left text-sm">
                        <thead className="bg-slate-50 text-slate-400 font-bold text-xs uppercase tracking-wider"><tr><th className="px-8 py-4">Team Volume Range</th><th className="px-8 py-4 text-right">Bonus (%)</th></tr></thead>
                        <tbody className="divide-y divide-slate-100">
                          {compPlan.bonuses.map((bonus, idx) => (
                            <tr key={idx}><td className="px-8 py-5 font-bold text-slate-700 whitespace-nowrap">₹{parseFloat(bonus.min_volume).toLocaleString('en-IN')} - ₹{parseFloat(bonus.max_volume).toLocaleString('en-IN')}</td><td className="px-8 py-5 text-right font-black text-amber-600 text-lg">{bonus.bonus_percentage}%</td></tr>
                          ))}
                        </tbody>
                      </table>
                    )}
                  </div>
                </div>
              </div>
              <div className="lg:col-span-2 break-inside-avoid">
                <div className="bg-white rounded-[2rem] shadow-[0_8px_30px_rgb(0,0,0,0.04)] border border-slate-100 overflow-hidden h-full">
                  <div className="px-8 py-6 border-b border-slate-100 bg-slate-50/50 flex items-center"><BarChart3 className="h-6 w-6 text-emerald-500 mr-3" /><h3 className="text-lg font-black text-slate-900">Level Generation Income</h3></div>
                  <div className="p-0">
                    {compPlan.levels.length === 0 ? <p className="text-sm font-medium text-slate-500 p-8">No level commissions set.</p> : (
                      <table className="w-full text-left text-sm">
                        <thead className="bg-slate-50 text-slate-400 font-bold text-xs uppercase tracking-wider"><tr><th className="px-8 py-4">Generation Level</th><th className="px-8 py-4">Commission %</th></tr></thead>
                        <tbody className="divide-y divide-slate-100">
                          {compPlan.levels.map((lvl, idx) => (
                            <tr key={idx} className="hover:bg-slate-50 transition-colors">
                              <td className="px-8 py-5"><div className="flex items-center"><span className="w-10 h-10 rounded-xl bg-emerald-100 text-emerald-700 font-black flex items-center justify-center mr-4">{lvl.level}</span><span className="font-bold text-slate-700">Level {lvl.level} Network</span></div></td>
                              <td className="px-8 py-5"><div className="flex items-center"><div className="w-full bg-slate-100 rounded-full h-3 mr-4 max-w-[120px] print:hidden"><div className="bg-emerald-500 h-3 rounded-full print:hidden shadow-inner" style={{ width: `${Math.min(lvl.commission_percentage, 100)}%` }}></div></div><span className="font-black text-emerald-600 text-lg">{lvl.commission_percentage}%</span></div></td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    )}
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    );
  };

  // ---------------------------------------------------------
  // 8. MY ORDERS TAB
  // ---------------------------------------------------------
  const OrdersTab = () => {
    const [orders, setOrders] = useState([]);
    const [isLoading, setIsLoading] = useState(true);
    const [activeInvoice, setActiveInvoice] = useState(null);

    useEffect(() => {
      const loadOrders = async () => {
        setIsLoading(true);
        const res = await fetchUserOrders();
        if (res.success) setOrders(res.data);
        setIsLoading(false);
      };
      loadOrders();
    }, []);

    const handlePrintInvoice = (order) => {
      setActiveInvoice(order);
      setTimeout(() => { window.print(); }, 150);
    };

    return (
      <div className={`max-w-6xl mx-auto space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500 ${activeInvoice ? 'print:hidden' : ''}`}>
        <div className="mb-8 flex justify-between items-end">
          <div><h2 className="text-3xl font-black text-slate-900 tracking-tight">My Orders & Invoices</h2><p className="text-slate-500 font-medium mt-1">View your purchase history and download individual GST receipts.</p></div>
        </div>

        <div className="bg-white rounded-[2rem] shadow-[0_8px_30px_rgb(0,0,0,0.04)] border border-slate-100 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-50 text-slate-400 font-bold border-b border-slate-100 uppercase tracking-wider text-xs">
                <tr><th className="px-8 py-5">Invoice ID</th><th className="px-8 py-5">Date</th><th className="px-8 py-5">Package Details</th><th className="px-8 py-5">Amount Paid</th><th className="px-8 py-5 text-center">Action</th></tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {isLoading ? <tr><td colSpan="5" className="px-8 py-12 text-center text-slate-400"><Loader2 className="h-8 w-8 animate-spin mx-auto mb-3 text-emerald-500" /> Syncing orders...</td></tr>
                : orders.length === 0 ? <tr><td colSpan="5" className="px-8 py-16 text-center text-slate-500"><Receipt className="h-12 w-12 text-slate-200 mx-auto mb-3"/>No purchases found.</td></tr>
                : orders.map((order, idx) => (
                  <tr key={idx} className="hover:bg-slate-50 transition-colors group">
                    <td className="px-8 py-6 font-mono text-slate-500 text-sm font-bold">#INV-{order.order_id.toString().padStart(6, '0')}</td>
                    <td className="px-8 py-6 text-slate-600 font-medium whitespace-nowrap">{new Date(order.created_at).toLocaleDateString('en-IN')}</td>
                    <td className="px-8 py-6 text-slate-900 font-black text-base">{order.package_name}</td>
                    <td className="px-8 py-6 font-black text-emerald-600 text-lg">₹{parseFloat(order.amount).toLocaleString('en-IN')}</td>
                    <td className="px-8 py-6 text-center"><button onClick={() => handlePrintInvoice(order)} className="inline-flex items-center justify-center px-4 py-2 bg-slate-100 text-slate-700 hover:bg-slate-900 hover:text-white rounded-xl transition-all text-sm font-bold shadow-sm"><Printer className="h-4 w-4 mr-2" /> Download PDF</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {activeInvoice && (
          <div className="hidden print:block absolute top-0 left-0 w-full bg-white text-black p-12 z-50 min-h-screen">
            <div className="flex justify-between items-start border-b-2 border-slate-200 pb-8 mb-8">
              <div>
                <h1 className="text-4xl font-black text-slate-900 tracking-tight">RK Trendz</h1>
                <p className="text-sm text-slate-500 mt-1">Network Marketing Platform</p>
                <div className="mt-4 text-sm text-slate-600"><p>101, Business Park Tower A</p><p>Andheri East, Mumbai 400069</p><p className="font-bold mt-1">GSTIN: <span className="font-mono text-slate-500">27AAACR0000A1Z5</span></p></div>
              </div>
              <div className="text-right">
                <h2 className="text-3xl font-bold text-slate-300 uppercase tracking-widest">Tax Invoice</h2>
                <p className="font-mono text-lg text-slate-800 mt-2">#INV-{activeInvoice.order_id.toString().padStart(6, '0')}</p>
                <p className="text-sm text-slate-500 mt-1">Date: {new Date(activeInvoice.created_at).toLocaleDateString()}</p>
              </div>
            </div>

            <div className="mb-10">
              <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">Billed To</h3>
              <p className="text-xl font-bold text-slate-900">{user.full_name}</p>
              <p className="text-slate-600">{user.email}</p>
              <p className="text-slate-600 mt-1">User ID: <span className="font-mono font-bold text-slate-800">#{user.id}</span></p>
            </div>

            <table className="w-full text-left mb-10">
              <thead className="bg-slate-50 border-y border-slate-200">
                <tr><th className="py-4 px-6 text-sm font-bold text-slate-700">Description</th><th className="py-4 px-6 text-sm font-bold text-slate-700 text-center">Qty</th><th className="py-4 px-6 text-sm font-bold text-slate-700 text-right">Total Amount</th></tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                <tr>
                  <td className="py-6 px-6"><p className="font-bold text-slate-900 text-lg">Digital Package: {activeInvoice.package_name}</p><p className="text-sm text-slate-500 mt-1">Platform activation & {activeInvoice.lucky_draw_coupons} Lucky Draw Coupons</p></td>
                  <td className="py-6 px-6 text-center font-bold text-slate-700">1</td>
                  <td className="py-6 px-6 text-right font-black text-slate-900 text-lg">₹{parseFloat(activeInvoice.amount).toLocaleString('en-IN')}</td>
                </tr>
              </tbody>
            </table>

            <div className="flex justify-end">
              <div className="w-1/2 border-t border-slate-200 pt-4">
                <div className="flex justify-between mb-3 text-sm text-slate-600"><span>Base Amount</span><span className="font-bold">₹{(parseFloat(activeInvoice.amount) / 1.18).toFixed(2)}</span></div>
                <div className="flex justify-between mb-5 text-sm text-slate-600"><span>IGST (18%)</span><span className="font-bold">₹{(parseFloat(activeInvoice.amount) - (parseFloat(activeInvoice.amount) / 1.18)).toFixed(2)}</span></div>
                <div className="flex justify-between items-center border-t-2 border-slate-800 pt-4"><span className="text-xl font-bold text-slate-900">Total Invoice Value</span><span className="text-3xl font-black text-slate-900">₹{parseFloat(activeInvoice.amount).toLocaleString('en-IN')}</span></div>
                <p className="text-right text-xs text-slate-400 mt-2 font-bold uppercase">(Inclusive of all taxes)</p>
              </div>
            </div>

            <div className="mt-32 pt-8 border-t border-slate-200 text-center">
              <p className="text-sm font-bold text-slate-800">For RK Trendz Pvt. Ltd.</p><p className="text-xs text-slate-500 mt-1">Authorized Signatory</p><p className="text-xs text-slate-400 mt-8 font-medium">This is a computer-generated invoice and does not require a physical signature.</p>
            </div>
          </div>
        )}
      </div>
    );
  };

  // ---------------------------------------------------------
  // 9. HELP & SUPPORT TAB
  // ---------------------------------------------------------
  const SupportTab = () => {
    const [tickets, setTickets] = useState([]);
    const [isLoading, setIsLoading] = useState(true);
    const [isTicketModalOpen, setIsTicketModalOpen] = useState(false);
    
    const [subject, setSubject] = useState("");
    const [message, setMessage] = useState("");
    const [isSubmitting, setIsSubmitting] = useState(false);

    useEffect(() => {
      const loadTickets = async () => {
        setIsLoading(true);
        const res = await fetchTickets();
        if (res.success) setTickets(res.data);
        setIsLoading(false);
      };
      loadTickets();
    }, []);

    const handleCreateTicket = async (e) => {
      e.preventDefault();
      setIsSubmitting(true);
      const res = await createTicket(subject, message);
      if (res.success) {
        setSubject(""); setMessage(""); setIsTicketModalOpen(false);
        const updatedRes = await fetchTickets();
        if (updatedRes.success) setTickets(updatedRes.data);
        alert(res.message);
      } else {
        alert(res.message);
      }
      setIsSubmitting(false);
    };

    return (
      <div className="max-w-6xl mx-auto space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
        <div className="mb-8 flex flex-col sm:flex-row justify-between sm:items-end gap-4">
          <div><h2 className="text-3xl font-black text-slate-900 tracking-tight">Help & Support</h2><p className="text-slate-500 font-medium mt-1">Need assistance? Open a ticket to reach our dedicated admin team.</p></div>
          <button onClick={() => setIsTicketModalOpen(true)} className="flex items-center justify-center px-6 py-3 bg-slate-900 text-white font-bold rounded-xl shadow-lg hover:shadow-xl hover:bg-slate-800 transition-all hover:-translate-y-1"><Plus className="h-5 w-5 mr-2" /> Open New Ticket</button>
        </div>

        <div className="bg-white rounded-[2rem] shadow-[0_8px_30px_rgb(0,0,0,0.04)] border border-slate-100 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-50 text-slate-400 font-bold border-b border-slate-100 uppercase tracking-wider text-xs">
                <tr><th className="px-8 py-5">Ticket ID</th><th className="px-8 py-5">Subject</th><th className="px-8 py-5">Date Opened</th><th className="px-8 py-5 text-center">Status</th></tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {isLoading ? (
                  <tr><td colSpan="4" className="px-8 py-12 text-center text-slate-400"><Loader2 className="h-8 w-8 animate-spin mx-auto mb-3 text-indigo-500" /> Syncing tickets...</td></tr>
                ) : tickets.length === 0 ? (
                  <tr><td colSpan="4" className="px-8 py-16 text-center text-slate-500"><LifeBuoy className="h-12 w-12 text-slate-200 mx-auto mb-3" />You have no active support tickets.</td></tr>
                ) : (
                  tickets.map((ticket, idx) => (
                    <tr key={idx} className="hover:bg-slate-50 transition-colors group">
                      <td className="px-8 py-6 font-mono text-slate-500 text-sm font-bold">#TKT-{ticket.id}</td>
                      <td className="px-8 py-6 text-slate-900 font-black text-base">{ticket.subject}</td>
                      <td className="px-8 py-6 text-slate-600 font-medium whitespace-nowrap">{new Date(ticket.created_at || ticket.date).toLocaleDateString('en-IN')}</td>
                      <td className="px-8 py-6 text-center"><span className={`px-4 py-2 text-xs font-bold rounded-xl ${ticket.status === 'Open' ? 'bg-amber-100 text-amber-800' : 'bg-emerald-100 text-emerald-800'}`}>{ticket.status}</span></td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* CREATE TICKET MODAL */}
        {isTicketModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-md animate-in fade-in">
            <div className="bg-white rounded-3xl shadow-2xl w-full max-w-md overflow-hidden animate-in zoom-in-95">
              <div className="px-8 py-6 border-b border-slate-100 flex justify-between items-center bg-slate-50"><h3 className="text-xl font-black text-slate-900">Create Support Ticket</h3><button onClick={() => setIsTicketModalOpen(false)} className="text-slate-400 hover:text-slate-900 bg-white p-2 rounded-full shadow-sm transition-colors"><X className="h-5 w-5" /></button></div>
              <div className="p-8 space-y-6">
                <form onSubmit={handleCreateTicket} className="space-y-5">
                  <div><label className="block text-sm font-bold text-slate-700 mb-2">Subject</label><input type="text" required value={subject} onChange={(e) => setSubject(e.target.value)} placeholder="e.g. Missing Withdrawal" className="w-full px-5 py-4 bg-slate-50 border border-slate-200 rounded-2xl font-medium focus:ring-2 focus:ring-indigo-500 transition-all" /></div>
                  <div><label className="block text-sm font-bold text-slate-700 mb-2">Message</label><textarea required rows="5" value={message} onChange={(e) => setMessage(e.target.value)} placeholder="Describe your issue in detail..." className="w-full px-5 py-4 bg-slate-50 border border-slate-200 rounded-2xl font-medium focus:ring-2 focus:ring-indigo-500 transition-all resize-none"></textarea></div>
                  <button type="submit" disabled={!subject || !message || isSubmitting} className="w-full py-4 px-6 bg-indigo-600 hover:bg-indigo-700 text-white font-black text-lg rounded-2xl shadow-xl transition-all disabled:opacity-50 flex justify-center hover:-translate-y-1">
                    {isSubmitting ? <Loader2 className="h-6 w-6 animate-spin" /> : "Submit Ticket"}
                  </button>
                </form>
              </div>
            </div>
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="min-h-screen bg-slate-50/50 flex font-sans selection:bg-emerald-100 selection:text-emerald-900">
      <aside className="hidden md:flex flex-col w-[19rem] bg-slate-950 text-slate-300 transition-all border-r border-slate-800 print:hidden relative overflow-hidden">
        <div className="absolute top-0 right-0 w-64 h-64 bg-emerald-500/5 rounded-full blur-3xl -translate-y-1/2 translate-x-1/2 pointer-events-none"></div>
        <div className="h-[5.5rem] flex items-center px-8 border-b border-slate-800/50 bg-slate-950/50 backdrop-blur-md relative z-10">
          <h1 className="text-[1.7rem] font-black text-white tracking-tighter">RK <span className="text-emerald-500">Trendz</span></h1>
        </div>
        <div className="flex-1 overflow-y-auto py-8 px-5 space-y-2 relative z-10 custom-scrollbar">
          {menuItems.map((item) => (
            <button
              key={item.name}
              onClick={() => switchTab(item.name)}
              className={`w-full flex items-center px-5 py-4 text-[0.95rem] font-bold rounded-2xl transition-all duration-300 ${
                activeTab === item.name ? "bg-gradient-to-r from-emerald-500 to-teal-500 text-white shadow-lg shadow-emerald-500/25 translate-x-2" : "hover:bg-slate-900 hover:text-white hover:translate-x-1"
              }`}
            >
              <item.icon className={`mr-4 h-[1.15rem] w-[1.15rem] ${activeTab === item.name ? "text-white" : "text-slate-500"}`} />
              {item.label || item.name}
            </button>
          ))}
        </div>
        <div className="p-6 border-t border-slate-800/50 relative z-10">
          <button onClick={logout} className="w-full flex items-center justify-center px-4 py-4 text-sm font-black text-red-400 bg-red-500/5 rounded-2xl hover:bg-red-500/10 hover:text-red-300 transition-all border border-red-500/10 hover:border-red-500/20">
            <LogOut className="mr-3 h-5 w-5" /> Secure Logout
          </button>
        </div>
      </aside>

      <main className="flex-1 flex flex-col min-w-0 overflow-hidden print:bg-white print:m-0 print:p-0">
        <header className="h-[5.5rem] flex items-center justify-between px-8 lg:px-12 border-b border-slate-200/80 bg-white/80 backdrop-blur-xl shrink-0 print:hidden z-20 sticky top-0 shadow-[0_4px_20px_rgb(0,0,0,0.02)]">
           <div className="flex items-center md:hidden"><h1 className="text-2xl font-black text-slate-900 tracking-tighter">RK <span className="text-emerald-500">Trendz</span></h1></div>
           <div className="hidden md:block">
              <h2 className="text-xl font-black text-slate-800">{activeTab}</h2>
           </div>
           <div className="ml-auto flex items-center gap-4">
              <button onClick={() => window.location.reload()} className="flex items-center px-5 py-2.5 text-sm font-bold text-slate-600 bg-slate-50 border border-slate-200 rounded-xl shadow-sm hover:bg-emerald-50 hover:text-emerald-600 hover:border-emerald-200 transition-all">
                 <RefreshCw className="h-4 w-4 sm:mr-2" /><span className="hidden sm:inline">Sync Data</span>
              </button>
              <button onClick={logout} className="md:hidden p-3 text-slate-400 hover:text-red-500 bg-slate-50 rounded-xl border border-slate-200 shadow-sm"><LogOut className="h-5 w-5" /></button>
           </div>
        </header>

        <div className="flex-1 overflow-y-auto p-6 lg:p-12 print:p-0 print:overflow-visible relative">
          {activeTab === "Overview" && <OverviewTab />}
          {activeTab === "Company Info" && <CompanyProfileTab />}
          {activeTab === "My Profile" && <ProfileTab />}
          {activeTab === "KYC Verification" && <KycTab />}
          {activeTab === "Wallet & Payouts" && <WalletTab />}
          {activeTab === "My Network Tree" && <><MyTeam /><NetworkTab /></>}
          {activeTab === "Product Catalog" && <Storefront onOrderPlaced={() => setActiveTab("My Orders & Invoices")} />}
          {activeTab === "My Orders & Invoices" && <MyStoreOrders />}
          {activeTab === "Help & Support" && <SupportTab />}
        </div>
      </main>

      <style jsx global>{`
        .custom-scrollbar::-webkit-scrollbar { width: 6px; height: 6px; }
        .custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
        .custom-scrollbar::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 10px; }
        .custom-scrollbar::-webkit-scrollbar-thumb:hover { background: #94a3b8; }
      `}</style>
    </div>
  );
}
