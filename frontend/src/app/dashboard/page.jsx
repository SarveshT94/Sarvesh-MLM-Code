"use client";

import { useEffect, useState, useRef } from "react";
import useAuthStore from "@/store/authStore";
import { useRouter } from "next/navigation";
import { requestProfileUpdate, verifyProfileOtp } from "@/services/profile";
import { fetchWalletData, submitWithdrawal, submitP2PTransfer } from "@/services/wallet";
import { fetchNetworkData } from "@/services/team";
import { fetchPackages, purchasePlan, fetchCompensationPlan, fetchUserOrders } from "@/services/package";
import { fetchUserRank } from "@/services/gamification"; 
import { fetchTickets, createTicket } from "@/services/support"; 
import { 
  LayoutDashboard, UserCircle, Users, ShoppingBag, 
  Wallet, LogOut, Share2, Copy, CheckCircle2, TrendingUp, Camera, ShieldCheck, 
  AlertCircle, Loader2, GitMerge, UserPlus, X, Zap, BarChart3, Target, Globe, 
  RefreshCw, Download, Receipt, Printer, ArrowRightLeft, LifeBuoy, Award, Plus, MessageSquare, Image as ImageIcon,
  Info
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
    { name: "My Profile", icon: UserCircle },
    { name: "My Network Tree", icon: Users },
    { name: "Wallet & Payouts", icon: Wallet },
    { name: "Product Catalog", icon: ShoppingBag },
    { name: "My Orders & Invoices", icon: Receipt },
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
      <>
        <div className="mb-8 print:hidden">
          <h2 className="text-2xl font-bold text-slate-900 sm:text-3xl">Welcome back, {user.full_name.split(' ')[0]}! 👋</h2>
          <p className="mt-1 text-sm text-slate-500">Here is your network and financial overview for today.</p>
        </div>

        <div className="bg-gradient-to-r from-slate-900 to-indigo-900 rounded-2xl shadow-lg border border-slate-800 p-6 mb-8 text-white print:hidden relative overflow-hidden">
          <div className="relative z-10">
            <div className="flex justify-between items-center mb-5">
              <div className="flex items-center">
                <div className="p-2 bg-white/10 rounded-lg mr-3 backdrop-blur-sm"><Award className="h-6 w-6 text-amber-400" /></div>
                <div>
                  <p className="text-xs text-slate-400 font-bold uppercase tracking-wider mb-0.5">Current Rank</p>
                  <h3 className="font-black text-xl text-white tracking-tight">{rankData.current_rank}</h3>
                </div>
              </div>
              {rankData.next_rank !== "Max Rank Reached" && (
                <span className="text-xs font-bold bg-white/20 border border-white/10 px-3 py-1.5 rounded-full text-slate-100 shadow-sm backdrop-blur-sm">
                  Next: {rankData.next_rank}
                </span>
              )}
            </div>
            
            <div className="w-full bg-slate-800/50 border border-slate-700 rounded-full h-3.5 mb-2 overflow-hidden shadow-inner">
              <div className="bg-gradient-to-r from-emerald-400 to-emerald-500 h-full rounded-full relative transition-all duration-1000 ease-out" style={{width: `${rankData.progress_percentage}%`}}>
                <div className="absolute inset-0 bg-white/20 animate-pulse"></div>
              </div>
            </div>
            <div className="flex justify-between items-center text-xs font-medium">
              <span className="text-emerald-400">₹{rankData.current_volume.toLocaleString('en-IN')} Vol.</span>
              <span className="text-slate-400">
                {rankData.next_rank !== "Max Rank Reached" ? `₹${rankData.next_rank_volume.toLocaleString('en-IN')} Target` : "Maximum Rank Achieved!"}
              </span>
            </div>
          </div>
          <Target className="absolute -right-6 -top-6 h-32 w-32 text-white/5 rotate-12" />
        </div>

        <div className="grid grid-cols-1 gap-5 sm:grid-cols-3 mb-8 print:hidden">
          <div className="bg-white overflow-hidden shadow-sm border border-slate-200 rounded-2xl relative">
            <div className="p-5"><div className="flex items-center"><div className="flex-shrink-0 bg-emerald-100 rounded-xl p-3"><Wallet className="h-6 w-6 text-emerald-600" /></div><div className="ml-5 w-0 flex-1"><dl><dt className="text-sm font-medium text-slate-500 truncate">Total Wallet Balance</dt><dd className="text-2xl font-bold text-slate-900 mt-1">Check Wallet</dd></dl></div></div></div>
            <div className="bg-slate-50 px-5 py-3 border-t border-slate-100"><button onClick={() => switchTab("Wallet & Payouts")} className="text-sm font-semibold text-emerald-600 hover:text-emerald-700 flex items-center">Request Withdrawal <TrendingUp className="ml-1 h-4 w-4" /></button></div>
          </div>
          <div className="bg-white overflow-hidden shadow-sm border border-slate-200 rounded-2xl">
            <div className="p-5"><div className="flex items-center"><div className="flex-shrink-0 bg-blue-100 rounded-xl p-3"><Users className="h-6 w-6 text-blue-600" /></div><div className="ml-5 w-0 flex-1"><dl><dt className="text-sm font-medium text-slate-500 truncate">Active Downline</dt><dd className="text-2xl font-bold text-slate-900 mt-1">View Network</dd></dl></div></div></div>
            <div className="bg-slate-50 px-5 py-3 border-t border-slate-100"><button onClick={() => switchTab("My Network Tree")} className="text-sm font-semibold text-blue-600 hover:text-blue-700">View Network Tree</button></div>
          </div>
          <div className="bg-white overflow-hidden shadow-sm border border-slate-200 rounded-2xl">
            <div className="p-5"><div className="flex items-center"><div className="flex-shrink-0 bg-purple-100 rounded-xl p-3"><CheckCircle2 className="h-6 w-6 text-purple-600" /></div><div className="ml-5 w-0 flex-1"><dl><dt className="text-sm font-medium text-slate-500 truncate">Current Plan</dt><dd className="text-xl font-bold text-slate-900 mt-1">Free Tier</dd></dl></div></div></div>
            <div className="bg-slate-50 px-5 py-3 border-t border-slate-100"><button onClick={() => switchTab("Product Catalog")} className="text-sm font-semibold text-purple-600 hover:text-purple-700">Upgrade Plan</button></div>
          </div>
        </div>

        <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 mb-8 lg:w-2/3 print:hidden">
          <h3 className="text-lg font-bold text-slate-900 mb-4">Grow Your Network</h3>
          <p className="text-sm text-slate-500 mb-5">Share your unique referral code with friends. You will earn commissions when they join and activate a plan.</p>
          <div className="flex flex-col sm:flex-row gap-4">
            <div className="flex-1 bg-slate-50 border border-slate-200 rounded-lg p-4 flex items-center justify-between">
              <div><p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">Your Referral Code</p><p className="text-xl font-black text-emerald-600 tracking-widest">{refCode}</p></div>
              <button onClick={handleCopy} disabled={refCode === "PENDING"} className="p-2 bg-white border border-slate-200 rounded-md hover:bg-slate-50 transition-colors shadow-sm text-slate-600 disabled:opacity-50">{copied ? <CheckCircle2 className="h-5 w-5 text-emerald-500" /> : <Copy className="h-5 w-5" />}</button>
            </div>
            <button onClick={handleShare} disabled={refCode === "PENDING"} className="flex items-center justify-center px-6 py-4 bg-emerald-600 hover:bg-emerald-700 text-white font-bold rounded-lg shadow-md transition-all sm:w-auto disabled:opacity-50"><Share2 className="mr-2 h-5 w-5" /> Share Link</button>
          </div>
        </div>
      </>
    );
  };

  // ---------------------------------------------------------
  // 2. PROFILE TAB
  // ---------------------------------------------------------
  const ProfileTab = () => {
    const currentEmail = user.email || "";
    const currentPhone = user.phone || "";

    const [form, setForm] = useState({ email: currentEmail, phone: currentPhone });
    const [photoPreview, setPhotoPreview] = useState(null);
    const fileInputRef = useRef(null);
    const [activeVerification, setActiveVerification] = useState(null);
    const [otpCode, setOtpCode] = useState("");
    const [isLoading, setIsLoading] = useState(false);
    const [status, setStatus] = useState({ type: "", msg: "" });

    const isEmailChanged = form.email !== currentEmail && form.email.includes("@");
    const isPhoneChanged = form.phone !== currentPhone && form.phone.length >= 10;

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

    return (
      <div className="max-w-4xl mx-auto space-y-6">
        {status.msg && (
          <div className={`p-4 rounded-lg border-l-4 flex items-center ${status.type === 'error' ? 'bg-red-50 border-red-500 text-red-700' : 'bg-emerald-50 border-emerald-500 text-emerald-700'}`}>
            {status.type === 'error' ? <AlertCircle className="h-5 w-5 mr-3" /> : <ShieldCheck className="h-5 w-5 mr-3" />}
            <p className="text-sm font-medium">{status.msg}</p>
          </div>
        )}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="md:col-span-1 space-y-6">
            <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 text-center">
              <div className="relative inline-block mb-4 group cursor-pointer" onClick={() => fileInputRef.current.click()}>
                <div className="h-32 w-32 rounded-full overflow-hidden border-4 border-slate-50 bg-slate-100 shadow-md">
                  {photoPreview ? <img src={photoPreview} alt="Profile" className="h-full w-full object-cover" /> : <div className="h-full w-full flex items-center justify-center bg-emerald-100 text-emerald-600 text-4xl font-bold">{user.full_name.charAt(0).toUpperCase()}</div>}
                </div>
                <div className="absolute inset-0 bg-slate-900/40 rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"><Camera className="h-8 w-8 text-white" /></div>
                <input type="file" ref={fileInputRef} onChange={handlePhotoChange} accept="image/*" className="hidden" />
              </div>
              <h3 className="text-xl font-bold text-slate-900">{user.full_name}</h3>
              <p className="text-sm font-medium text-emerald-600 bg-emerald-50 inline-block px-3 py-1 rounded-full mt-2 border border-emerald-100">Profile Settings</p>
            </div>
          </div>
          <div className="md:col-span-2 space-y-6">
            <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
              <div className="px-6 py-5 border-b border-slate-100 bg-slate-50/50">
                <h3 className="text-lg font-bold text-slate-900 flex items-center"><ShieldCheck className="h-5 w-5 mr-2 text-slate-400" /> Contact & Security</h3>
              </div>
              <div className="p-6 space-y-6">
                <div className="space-y-3">
                  <label className="block text-sm font-semibold text-slate-700">Email Address</label>
                  <div className="flex gap-3">
                    <input type="email" value={form.email} disabled={activeVerification === 'email'} onChange={(e) => setForm({ ...form, email: e.target.value })} className="flex-1 px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-lg text-slate-900 focus:ring-2 focus:ring-emerald-500 disabled:opacity-60" />
                    <button onClick={() => handleRequestOtp('email')} disabled={!isEmailChanged || isLoading || activeVerification === 'email'} className={`px-4 py-2.5 text-sm font-bold rounded-lg transition-colors flex items-center ${isEmailChanged && activeVerification !== 'email' ? "bg-slate-900 hover:bg-slate-800 text-white shadow-md" : "bg-slate-100 text-slate-400 cursor-not-allowed border border-slate-200"}`}>
                      {isLoading && activeVerification === 'email' ? <Loader2 className="h-4 w-4 animate-spin" /> : "Update"}
                    </button>
                  </div>
                  {activeVerification === 'email' && (
                    <div className="mt-3 p-4 bg-emerald-50 border border-emerald-100 rounded-lg flex gap-3 animate-in fade-in slide-in-from-top-2">
                      <input type="text" maxLength="6" placeholder="Enter 6-digit OTP" value={otpCode} onChange={(e) => setOtpCode(e.target.value.replace(/\D/g, ''))} className="flex-1 px-4 py-2 text-center tracking-widest font-mono text-lg border border-emerald-200 rounded-md focus:ring-2 focus:ring-emerald-500" />
                      <button onClick={handleVerifyOtp} disabled={isLoading || otpCode.length !== 6} className="px-6 py-2 bg-emerald-600 hover:bg-emerald-700 text-white font-bold rounded-md disabled:opacity-50 transition-colors">{isLoading ? <Loader2 className="h-5 w-5 animate-spin mx-auto" /> : "Confirm"}</button>
                    </div>
                  )}
                </div>
                <hr className="border-slate-100" />
                <div className="space-y-3">
                  <label className="block text-sm font-semibold text-slate-700">Phone Number</label>
                  <div className="flex gap-3">
                    <input type="text" value={form.phone} disabled={activeVerification === 'phone'} placeholder="+91 0000000000" onChange={(e) => setForm({ ...form, phone: e.target.value })} className="flex-1 px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-lg text-slate-900 focus:ring-2 focus:ring-emerald-500 disabled:opacity-60" />
                    <button onClick={() => handleRequestOtp('phone')} disabled={!isPhoneChanged || isLoading || activeVerification === 'phone'} className={`px-4 py-2.5 text-sm font-bold rounded-lg transition-colors flex items-center ${isPhoneChanged && activeVerification !== 'phone' ? "bg-slate-900 hover:bg-slate-800 text-white shadow-md" : "bg-slate-100 text-slate-400 cursor-not-allowed border border-slate-200"}`}>
                      {isLoading && activeVerification === 'phone' ? <Loader2 className="h-4 w-4 animate-spin" /> : "Update"}
                    </button>
                  </div>
                  {activeVerification === 'phone' && (
                    <div className="mt-3 p-4 bg-emerald-50 border border-emerald-100 rounded-lg flex gap-3 animate-in fade-in slide-in-from-top-2">
                      <input type="text" maxLength="6" placeholder="Enter 6-digit OTP" value={otpCode} onChange={(e) => setOtpCode(e.target.value.replace(/\D/g, ''))} className="flex-1 px-4 py-2 text-center tracking-widest font-mono text-lg border border-emerald-200 rounded-md focus:ring-2 focus:ring-emerald-500" />
                      <button onClick={handleVerifyOtp} disabled={isLoading || otpCode.length !== 6} className="px-6 py-2 bg-emerald-600 hover:bg-emerald-700 text-white font-bold rounded-md disabled:opacity-50 transition-colors">{isLoading ? <Loader2 className="h-5 w-5 animate-spin mx-auto" /> : "Confirm"}</button>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  };

  // ---------------------------------------------------------
  // 3. WALLET TAB (WITH CLICKABLE RECEIPTS)
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

    // 🔥 NEW: Transaction Details Modal State
    const [selectedTx, setSelectedTx] = useState(null);

    const loadWallet = async () => {
      setIsLoading(true);
      const res = await fetchWalletData(user.id); 
      if (res.success) { setBalance(res.balance); setTransactions(res.history); }
      setIsLoading(false);
    };

    useEffect(() => { if (user?.id) loadWallet(); }, []);

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
      <div className="max-w-5xl mx-auto space-y-6 relative">
        <div className="mb-8">
          <h2 className="text-2xl font-bold text-slate-900">Wallet & Earnings</h2>
          <p className="text-sm text-slate-500">Manage your commissions, withdrawals, and peer-to-peer transfers.</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="bg-gradient-to-br from-slate-900 to-slate-800 rounded-2xl shadow-lg border border-slate-700 p-6 text-white relative overflow-hidden">
            <div className="relative z-10">
              <p className="text-slate-400 font-medium text-sm mb-1 uppercase tracking-wider">Available Balance</p>
              <h3 className="text-4xl font-black tracking-tight mb-6">₹{isLoading ? "..." : parseFloat(balance).toFixed(2)}</h3>
              <div className="flex flex-wrap gap-3">
                <button onClick={() => setIsWithdrawModalOpen(true)} className="px-5 py-2.5 bg-emerald-500 hover:bg-emerald-600 text-white text-sm font-bold rounded-lg shadow-md flex items-center">
                  <TrendingUp className="h-4 w-4 mr-2" /> Withdraw
                </button>
                <button onClick={() => setIsTransferModalOpen(true)} className="px-5 py-2.5 bg-white/10 hover:bg-white/20 text-white border border-white/20 text-sm font-bold rounded-lg shadow-md flex items-center backdrop-blur-sm">
                  <ArrowRightLeft className="h-4 w-4 mr-2" /> Transfer Funds
                </button>
              </div>
            </div>
            <Wallet className="absolute -bottom-6 -right-6 h-48 w-48 text-slate-700/30 rotate-12" />
          </div>

          <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 flex flex-col justify-center">
            <div className="flex items-start mb-4">
              <div className="p-3 bg-blue-50 text-blue-600 rounded-lg shrink-0"><ArrowRightLeft className="h-6 w-6" /></div>
              <div className="ml-4">
                <h4 className="text-lg font-bold text-slate-900">Instant P2P Transfers</h4>
                <p className="text-sm text-slate-500 mt-1">Send wallet funds instantly to any registered user using their Email or User ID with zero transaction fees.</p>
              </div>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden mt-8">
          <div className="px-6 py-5 border-b border-slate-100 bg-slate-50/50 flex justify-between items-center">
            <h3 className="text-lg font-bold text-slate-900">Recent Transactions</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-50 text-slate-500 font-medium border-b border-slate-200">
                <tr><th className="px-6 py-4">Date</th><th className="px-6 py-4">Description</th><th className="px-6 py-4">Type</th><th className="px-6 py-4 text-right">Amount</th></tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {isLoading ? <tr><td colSpan="4" className="px-6 py-10 text-center text-slate-400"><Loader2 className="h-6 w-6 animate-spin mx-auto mb-2" /> Loading ledger...</td></tr>
                : transactions.length === 0 ? <tr><td colSpan="4" className="px-6 py-10 text-center text-slate-500">No transactions found.</td></tr>
                : transactions.map((tx, idx) => (
                  // 🔥 NEW: Made the row clickable!
                  <tr key={idx} onClick={() => setSelectedTx(tx)} className="hover:bg-slate-50 transition-colors cursor-pointer group">
                    <td className="px-6 py-4 text-slate-600 whitespace-nowrap">{new Date(tx.created_at).toLocaleDateString()}</td>
                    <td className="px-6 py-4 text-slate-900 font-medium group-hover:text-emerald-600 transition-colors flex items-center">
                      {tx.description || tx.reference} 
                      {tx.description?.toLowerCase().includes("package") && <ShoppingBag className="h-3 w-3 ml-2 text-slate-400" />}
                    </td>
                    <td className="px-6 py-4"><span className={`px-2.5 py-1 text-xs font-semibold rounded-full ${tx.transaction_type.includes('credit') || tx.transaction_type.includes('commission') || tx.transaction_type.includes('in') ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'}`}>{tx.transaction_type.replace(/_/g, ' ').toUpperCase()}</span></td>
                    <td className={`px-6 py-4 text-right font-bold whitespace-nowrap ${tx.amount > 0 ? "text-emerald-600" : "text-slate-900"}`}>{tx.amount > 0 ? "+" : ""}₹{parseFloat(Math.abs(tx.amount)).toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* 🔥 NEW: TRANSACTION RECEIPT MODAL */}
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

        {/* WITHDRAW MODAL */}
        {isWithdrawModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-in fade-in">
            <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md overflow-hidden animate-in zoom-in-95 max-h-[90vh] flex flex-col">
              <div className="px-6 py-4 border-b border-slate-100 flex justify-between items-center bg-slate-50 shrink-0">
                <h3 className="text-lg font-bold text-slate-900">Request Payout</h3>
                <button onClick={() => setIsWithdrawModalOpen(false)} className="text-slate-400 hover:text-slate-600 transition-colors"><X className="h-5 w-5" /></button>
              </div>
              <div className="p-6 overflow-y-auto space-y-6">
                {withdrawStatus.msg && <div className={`p-4 rounded-lg border-l-4 flex items-start ${withdrawStatus.type === 'error' ? 'bg-red-50 border-red-500 text-red-700' : 'bg-emerald-50 border-emerald-500 text-emerald-700'}`}><AlertCircle className="h-5 w-5 mr-3 shrink-0 mt-0.5" /><p className="text-sm font-medium">{withdrawStatus.msg}</p></div>}
                <div className="bg-slate-50 p-4 rounded-xl border border-slate-200 flex justify-between items-center">
                  <span className="text-sm font-semibold text-slate-500">Available Balance:</span><span className="text-lg font-black text-emerald-600">₹{parseFloat(balance).toFixed(2)}</span>
                </div>
                <form onSubmit={handleWithdraw} className="space-y-5">
                  <div>
                    <label className="block text-sm font-semibold text-slate-700 mb-1">Withdrawal Amount (₹)</label>
                    <input type="number" min="1" step="0.01" value={withdrawAmount} onChange={(e) => setWithdrawAmount(e.target.value)} placeholder="e.g. 1500" className="w-full px-4 py-3 bg-white border border-slate-300 rounded-lg text-slate-900 text-lg font-bold focus:ring-2 focus:ring-emerald-500" />
                  </div>
                  <div>
                    <label className="block text-sm font-semibold text-slate-700 mb-2">Select Payout Method</label>
                    <div className="flex gap-3">
                      <button type="button" onClick={() => setPayoutMethod('upi')} className={`flex-1 py-2.5 rounded-lg border text-sm font-bold transition-all ${payoutMethod === 'upi' ? 'bg-emerald-50 border-emerald-500 text-emerald-700' : 'bg-white border-slate-200 text-slate-500 hover:bg-slate-50'}`}>UPI Transfer</button>
                      <button type="button" onClick={() => setPayoutMethod('bank')} className={`flex-1 py-2.5 rounded-lg border text-sm font-bold transition-all ${payoutMethod === 'bank' ? 'bg-emerald-50 border-emerald-500 text-emerald-700' : 'bg-white border-slate-200 text-slate-500 hover:bg-slate-50'}`}>Bank Transfer</button>
                    </div>
                  </div>
                  {payoutMethod === 'upi' ? (
                    <div className="space-y-3 bg-slate-50 p-4 rounded-lg border border-slate-100">
                      <div><label className="block text-xs font-semibold text-slate-600 mb-1">UPI ID</label><input type="text" placeholder="example@upi" value={payoutDetails.upiId} onChange={(e) => setPayoutDetails({...payoutDetails, upiId: e.target.value})} className="w-full px-3 py-2 border border-slate-300 rounded-md text-sm" /></div>
                      <div><label className="block text-xs font-semibold text-slate-600 mb-1">UPI Linked Mobile Number</label><input type="text" placeholder="9876543210" value={payoutDetails.upiMobile} onChange={(e) => setPayoutDetails({...payoutDetails, upiMobile: e.target.value})} className="w-full px-3 py-2 border border-slate-300 rounded-md text-sm" /></div>
                    </div>
                  ) : (
                    <div className="space-y-3 bg-slate-50 p-4 rounded-lg border border-slate-100">
                      <div><label className="block text-xs font-semibold text-slate-600 mb-1">Bank Account Number</label><input type="text" placeholder="Account Number" value={payoutDetails.bankAccount} onChange={(e) => setPayoutDetails({...payoutDetails, bankAccount: e.target.value})} className="w-full px-3 py-2 border border-slate-300 rounded-md text-sm" /></div>
                      <div><label className="block text-xs font-semibold text-slate-600 mb-1">IFSC Code</label><input type="text" placeholder="IFSC Code" value={payoutDetails.bankIfsc} onChange={(e) => setPayoutDetails({...payoutDetails, bankIfsc: e.target.value})} className="w-full px-3 py-2 border border-slate-300 rounded-md text-sm" /></div>
                    </div>
                  )}
                  <button type="submit" disabled={isWithdrawing || !withdrawAmount} className="w-full py-3.5 px-4 bg-emerald-600 hover:bg-emerald-700 text-white font-bold rounded-lg shadow-md transition-all disabled:opacity-50 flex items-center justify-center mt-4">
                    {isWithdrawing ? <Loader2 className="h-5 w-5 animate-spin" /> : "Submit Withdrawal Request"}
                  </button>
                </form>
              </div>
            </div>
          </div>
        )}

        {/* TRANSFER MODAL */}
        {isTransferModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-in fade-in">
            <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md overflow-hidden animate-in zoom-in-95">
              <div className="px-6 py-4 border-b border-slate-100 flex justify-between items-center bg-slate-50"><h3 className="text-lg font-bold text-slate-900">Transfer Funds</h3><button onClick={() => setIsTransferModalOpen(false)} className="text-slate-400 hover:text-slate-600 transition-colors"><X className="h-5 w-5" /></button></div>
              <div className="p-6 space-y-6">
                {transferStatus.msg && <div className={`p-4 rounded-lg border-l-4 flex items-start ${transferStatus.type === 'error' ? 'bg-red-50 border-red-500 text-red-700' : 'bg-emerald-50 border-emerald-500 text-emerald-700'}`}><AlertCircle className="h-5 w-5 mr-3 shrink-0 mt-0.5" /><p className="text-sm font-medium">{transferStatus.msg}</p></div>}
                <div className="bg-slate-50 p-4 rounded-xl border border-slate-200 flex justify-between items-center"><span className="text-sm font-semibold text-slate-500">Available Balance:</span><span className="text-lg font-black text-slate-900">₹{parseFloat(balance).toFixed(2)}</span></div>
                <form onSubmit={handleTransfer} className="space-y-4">
                  <div><label className="block text-sm font-semibold text-slate-700 mb-1">Receiver User ID or Email</label><input type="text" value={transferReceiver} onChange={(e) => setTransferReceiver(e.target.value)} placeholder="e.g. 45 or john@email.com" className="w-full px-4 py-3 bg-white border border-slate-300 rounded-lg text-slate-900 font-medium focus:outline-none focus:ring-2 focus:ring-slate-900" /></div>
                  <div><label className="block text-sm font-semibold text-slate-700 mb-1">Transfer Amount (₹)</label><input type="number" min="1" step="0.01" value={transferAmount} onChange={(e) => setTransferAmount(e.target.value)} placeholder="e.g. 500" className="w-full px-4 py-3 bg-white border border-slate-300 rounded-lg text-slate-900 text-lg font-semibold focus:outline-none focus:ring-2 focus:ring-slate-900" /></div>
                  <button type="submit" disabled={isTransferring || !transferAmount || !transferReceiver} className="w-full py-3.5 px-4 bg-slate-900 hover:bg-slate-800 text-white font-bold rounded-lg shadow-md transition-all disabled:opacity-50 flex items-center justify-center">
                    {isTransferring ? <Loader2 className="h-5 w-5 animate-spin" /> : "Send Funds Instantly"}
                  </button>
                </form>
              </div>
            </div>
          </div>
        )}
      </div>
    );
  };

  // ---------------------------------------------------------
  // 4. NETWORK TAB
  // ---------------------------------------------------------
  const NetworkTab = () => {
    const [networkStats, setNetworkStats] = useState({ total: 0, direct: [] });
    const [treeData, setTreeData] = useState([]);
    const [isLoading, setIsLoading] = useState(true);

    useEffect(() => {
      const loadNetwork = async () => {
        setIsLoading(true);
        const res = await fetchNetworkData(user.id); 
        if (res.success) { setNetworkStats({ total: res.totalCount, direct: res.directTeam }); setTreeData(res.tree); }
        setIsLoading(false);
      };
      if (user?.id) loadNetwork();
    }, []);

    return (
      <div className="max-w-5xl mx-auto space-y-6">
        <div className="mb-8"><h2 className="text-2xl font-bold text-slate-900">My Network Tree</h2><p className="text-sm text-slate-500">Monitor your downline, direct referrals, and team growth.</p></div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 flex items-center"><div className="p-4 bg-blue-50 text-blue-600 rounded-xl"><GitMerge className="h-8 w-8" /></div><div className="ml-5"><p className="text-sm font-medium text-slate-500">Total Network Size</p><h3 className="text-3xl font-black text-slate-900 mt-1">{isLoading ? "..." : networkStats.total} <span className="text-base font-medium text-slate-500">Members</span></h3></div></div>
          <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 flex items-center"><div className="p-4 bg-emerald-50 text-emerald-600 rounded-xl"><UserPlus className="h-8 w-8" /></div><div className="ml-5"><p className="text-sm font-medium text-slate-500">Direct Referrals</p><h3 className="text-3xl font-black text-slate-900 mt-1">{isLoading ? "..." : networkStats.direct.length} <span className="text-base font-medium text-slate-500">Directs</span></h3></div></div>
        </div>
        <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden mt-8">
          <div className="px-6 py-5 border-b border-slate-100 bg-slate-50/50 flex justify-between items-center"><h3 className="text-lg font-bold text-slate-900">Downline Directory</h3></div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-50 text-slate-500 font-medium border-b border-slate-200">
                <tr><th className="px-6 py-4">Member Name</th><th className="px-6 py-4 text-center">Level</th><th className="px-6 py-4">Join Date</th><th className="px-6 py-4">Status</th></tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {isLoading ? <tr><td colSpan="4" className="px-6 py-10 text-center text-slate-400"><Loader2 className="h-6 w-6 animate-spin mx-auto mb-2" /> Loading network tree...</td></tr>
                : treeData.length === 0 ? <tr><td colSpan="4" className="px-6 py-10 text-center text-slate-500">Your network is empty. Share your link!</td></tr>
                : treeData.map((member, idx) => (
                  <tr key={idx} className="hover:bg-slate-50 transition-colors">
                    <td className="px-6 py-4"><div className="flex items-center"><div className="h-8 w-8 rounded-full bg-slate-200 flex items-center justify-center text-slate-600 font-bold mr-3">{(member.full_name || member.name || "U")[0].toUpperCase()}</div><span className="text-slate-900 font-medium">{member.full_name || member.name || `User #${member.id}`}</span></div></td>
                    <td className="px-6 py-4 text-center"><span className="px-3 py-1 bg-blue-50 text-blue-700 rounded-full font-bold text-xs">Lvl {member.level || 1}</span></td>
                    <td className="px-6 py-4 text-slate-600 whitespace-nowrap">{member.created_at ? new Date(member.created_at).toLocaleDateString() : "N/A"}</td>
                    <td className="px-6 py-4"><span className={`px-2.5 py-1 text-xs font-semibold rounded-full ${member.is_active || member.status === 'active' ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-600'}`}>{member.is_active || member.status === 'active' ? 'Active' : 'Inactive'}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    );
  };

  // ---------------------------------------------------------
  // 5. PRODUCT CATALOG TAB
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
        if (compRes.success && compRes.data) {
          setCompPlan({ global: compRes.data.global || [], levels: compRes.data.levels || [], bonuses: compRes.data.bonuses || [] });
        }
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
      <div className="max-w-6xl mx-auto space-y-12 pb-12 relative">
        {showSuccessModal && purchasedPlanDetails && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/70 backdrop-blur-sm animate-in fade-in print:hidden">
            <div className="bg-white rounded-3xl shadow-2xl w-full max-w-md overflow-hidden animate-in zoom-in-95 text-center p-8">
              <div className="w-20 h-20 bg-emerald-100 rounded-full flex items-center justify-center mx-auto mb-6"><CheckCircle2 className="h-10 w-10 text-emerald-600" /></div>
              <h2 className="text-2xl font-black text-slate-900 mb-2">Payment Successful!</h2>
              <p className="text-slate-500 mb-6">You have successfully activated the <span className="font-bold text-slate-900">{purchasedPlanDetails.name}</span> plan. Your commission engine is now live.</p>
              <div className="bg-slate-50 p-4 rounded-xl border border-slate-100 mb-8 text-left">
                <div className="flex justify-between items-center mb-2"><span className="text-sm text-slate-500 font-medium">Amount Paid</span><span className="font-bold text-slate-900">₹{parseFloat(purchasedPlanDetails.price).toLocaleString('en-IN')}</span></div>
                <div className="flex justify-between items-center"><span className="text-sm text-slate-500 font-medium">Status</span><span className="text-xs font-bold bg-emerald-100 text-emerald-700 px-2.5 py-0.5 rounded-full">Activated</span></div>
              </div>
              <button onClick={() => { setShowSuccessModal(false); switchTab("My Orders & Invoices"); }} className="w-full py-3.5 bg-slate-900 hover:bg-slate-800 text-white font-bold rounded-xl shadow-md transition-all">
                View My Invoice
              </button>
            </div>
          </div>
        )}

        <div>
          <div className="flex flex-col sm:flex-row sm:justify-between sm:items-end mb-8 gap-4 print:hidden">
            <div><h2 className="text-2xl font-bold text-slate-900">Product Catalog</h2><p className="text-sm text-slate-500">Choose an activation plan to unlock your earning potential.</p></div>
            <button onClick={() => window.print()} className="print:hidden flex items-center px-5 py-2.5 bg-indigo-50 border border-indigo-100 text-indigo-700 hover:bg-indigo-100 hover:border-indigo-200 rounded-lg shadow-sm font-bold text-sm transition-all">
              <Download className="h-4 w-4 mr-2" /> Download PDF Brochure
            </button>
          </div>
          {buyStatus.msg && <div className={`p-4 mb-6 rounded-xl border flex items-center print:hidden ${buyStatus.type === 'error' ? 'bg-red-50 border-red-200 text-red-700' : 'bg-emerald-50 border-emerald-200 text-emerald-700'}`}><AlertCircle className="h-5 w-5 mr-3 shrink-0" /><p className="font-semibold">{buyStatus.msg}</p></div>}
          
          {isLoading ? <div className="flex flex-col items-center justify-center h-64 print:hidden"><Loader2 className="h-10 w-10 text-emerald-500 animate-spin mb-4" /><p className="text-slate-500 font-medium">Loading catalog...</p></div>
          : packages.length === 0 ? <div className="text-center p-10 bg-white rounded-2xl border border-slate-200 shadow-sm print:hidden"><ShoppingBag className="h-12 w-12 text-slate-300 mx-auto mb-4" /><h3 className="text-lg font-bold text-slate-900">No Plans Available</h3></div>
          : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
              {packages.map((pkg) => (
                <div key={pkg.id} className={`bg-white rounded-2xl shadow-sm border ${pkg.is_popular ? 'border-emerald-500 shadow-emerald-100' : 'border-slate-200'} relative overflow-hidden flex flex-col`}>
                  {pkg.is_popular && <div className="absolute top-0 inset-x-0 bg-emerald-500 text-white text-xs font-bold uppercase tracking-widest text-center py-1.5 z-10">Most Popular</div>}
                  
                  <div className="h-48 bg-slate-100 relative border-b border-slate-200">
                     {pkg.image_url ? (
                       <img src={pkg.image_url} alt={pkg.name} className="w-full h-full object-cover" />
                     ) : (
                       <div className="flex items-center justify-center h-full text-slate-300">
                         <ImageIcon className="h-16 w-16 opacity-30" />
                       </div>
                     )}
                  </div>

                  <div className="p-8 pb-4">
                    <h3 className="text-2xl font-black text-slate-900">{pkg.name}</h3>
                    <div className="mt-2 flex items-baseline text-4xl font-black text-emerald-600"><span className="text-2xl mr-1">₹</span>{parseFloat(pkg.price).toFixed(0)}</div>
                    <p className="text-slate-500 mt-2 text-sm">One-time activation fee</p>
                  </div>
                  <div className="p-8 pt-0 flex-1 flex flex-col">
                    <ul className="space-y-4 flex-1">
                      <li className="flex items-start"><Zap className="h-5 w-5 text-amber-500 mr-3 shrink-0" /><span className="text-sm font-medium text-slate-700">Unlock {pkg.lucky_draw_coupons || 0} Lucky Draw Coupons</span></li>
                      <li className="flex items-start"><CheckCircle2 className="h-5 w-5 text-emerald-500 mr-3 shrink-0" /><span className="text-sm font-medium text-slate-700">Access to Multi-Level Commissions</span></li>
                    </ul>
                    <button onClick={() => handleBuy(pkg)} disabled={isPurchasing} className={`print:hidden mt-8 w-full py-3.5 px-4 rounded-lg font-bold shadow-md transition-all flex items-center justify-center ${pkg.is_popular ? 'bg-emerald-600 hover:bg-emerald-700 text-white disabled:bg-emerald-400' : 'bg-slate-900 hover:bg-slate-800 text-white disabled:bg-slate-700'}`}>
                      {isPurchasing ? <Loader2 className="h-5 w-5 animate-spin" /> : "Purchase & Activate"}
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
            <div className="mb-8"><h2 className="text-2xl font-bold text-slate-900">Platform Earning Rules</h2><p className="text-sm text-slate-500">Your transparent, real-time compensation structure.</p></div>
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
              <div className="lg:col-span-1 space-y-6 break-inside-avoid">
                <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
                  <div className="px-6 py-5 border-b border-slate-100 bg-slate-50/50 flex items-center"><Globe className="h-5 w-5 text-indigo-500 mr-3" /><h3 className="text-lg font-bold text-slate-900">Global Commissions</h3></div>
                  <div className="p-6">
                    {compPlan.global.length === 0 ? <p className="text-sm text-slate-500">No global rules set.</p> : (
                      <ul className="space-y-4">
                        {compPlan.global.map((item, idx) => (
                          <li key={idx} className="flex justify-between items-center"><span className="text-sm font-medium text-slate-700 capitalize">{item.setting_key.replace(/_/g, ' ')}</span><span className="text-base font-black text-indigo-600">{item.percentage_value}%</span></li>
                        ))}
                      </ul>
                    )}
                  </div>
                </div>
                <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden break-inside-avoid">
                  <div className="px-6 py-5 border-b border-slate-100 bg-slate-50/50 flex items-center"><Target className="h-5 w-5 text-amber-500 mr-3" /><h3 className="text-lg font-bold text-slate-900">Target Bonuses</h3></div>
                  <div className="p-0">
                    {compPlan.bonuses.length === 0 ? <p className="text-sm text-slate-500 p-6">No bonuses set.</p> : (
                      <table className="w-full text-left text-sm">
                        <thead className="bg-slate-50 text-slate-500 font-medium"><tr><th className="px-6 py-3">Team Volume Range</th><th className="px-6 py-3 text-right">Bonus (%)</th></tr></thead>
                        <tbody className="divide-y divide-slate-100">
                          {compPlan.bonuses.map((bonus, idx) => (
                            <tr key={idx}><td className="px-6 py-3 font-medium text-slate-700 whitespace-nowrap">₹{parseFloat(bonus.min_volume).toLocaleString('en-IN')} - ₹{parseFloat(bonus.max_volume).toLocaleString('en-IN')}</td><td className="px-6 py-3 text-right font-black text-amber-600">{bonus.bonus_percentage}%</td></tr>
                          ))}
                        </tbody>
                      </table>
                    )}
                  </div>
                </div>
              </div>
              <div className="lg:col-span-2 break-inside-avoid">
                <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden h-full">
                  <div className="px-6 py-5 border-b border-slate-100 bg-slate-50/50 flex items-center"><BarChart3 className="h-5 w-5 text-emerald-500 mr-3" /><h3 className="text-lg font-bold text-slate-900">Level Generation Income</h3></div>
                  <div className="p-0">
                    {compPlan.levels.length === 0 ? <p className="text-sm text-slate-500 p-6">No level commissions set.</p> : (
                      <table className="w-full text-left text-sm">
                        <thead className="bg-slate-50 text-slate-500 font-medium"><tr><th className="px-6 py-4">Generation Level</th><th className="px-6 py-4">Commission %</th></tr></thead>
                        <tbody className="divide-y divide-slate-100">
                          {compPlan.levels.map((lvl, idx) => (
                            <tr key={idx} className="hover:bg-slate-50 transition-colors">
                              <td className="px-6 py-4"><div className="flex items-center"><span className="w-8 h-8 rounded bg-emerald-100 text-emerald-700 font-bold flex items-center justify-center mr-3">{lvl.level}</span><span className="font-semibold text-slate-700">Level {lvl.level} Network</span></div></td>
                              <td className="px-6 py-4"><div className="flex items-center"><div className="w-full bg-slate-100 rounded-full h-2.5 mr-3 max-w-[100px] print:hidden"><div className="bg-emerald-500 h-2.5 rounded-full print:hidden" style={{ width: `${Math.min(lvl.commission_percentage, 100)}%` }}></div></div><span className="font-black text-emerald-600">{lvl.commission_percentage}%</span></div></td>
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
  // 6. MY ORDERS TAB
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
      <>
        <div className={`max-w-5xl mx-auto space-y-6 ${activeInvoice ? 'print:hidden' : ''}`}>
          <div className="mb-8 flex justify-between items-end">
            <div><h2 className="text-2xl font-bold text-slate-900">My Orders & Invoices</h2><p className="text-sm text-slate-500">View your purchase history and download individual GST receipts.</p></div>
          </div>

          <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="bg-slate-50 text-slate-500 font-medium border-b border-slate-200">
                  <tr><th className="px-6 py-4">Invoice ID</th><th className="px-6 py-4">Date</th><th className="px-6 py-4">Package Details</th><th className="px-6 py-4">Amount Paid</th><th className="px-6 py-4 text-center">Action</th></tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {isLoading ? <tr><td colSpan="5" className="px-6 py-10 text-center text-slate-400"><Loader2 className="h-6 w-6 animate-spin mx-auto mb-2" /> Loading history...</td></tr>
                  : orders.length === 0 ? <tr><td colSpan="5" className="px-6 py-10 text-center text-slate-500">No purchases found. Visit the Product Catalog to get started!</td></tr>
                  : orders.map((order, idx) => (
                    <tr key={idx} className="hover:bg-slate-50 transition-colors">
                      <td className="px-6 py-4 font-mono text-slate-500 text-xs">#INV-{order.order_id.toString().padStart(6, '0')}</td>
                      <td className="px-6 py-4 text-slate-600 whitespace-nowrap">{new Date(order.created_at).toLocaleDateString()}</td>
                      <td className="px-6 py-4 text-slate-900 font-bold">{order.package_name}</td>
                      <td className="px-6 py-4 font-black text-emerald-600">₹{parseFloat(order.amount).toLocaleString('en-IN')}</td>
                      <td className="px-6 py-4 text-center"><button onClick={() => handlePrintInvoice(order)} className="inline-flex items-center justify-center px-3 py-1.5 bg-slate-900 text-white rounded hover:bg-slate-800 transition-colors text-xs font-bold"><Printer className="h-3 w-3 mr-1.5" /> PDF</button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {activeInvoice && (
          <div className="hidden print:block absolute top-0 left-0 w-full bg-white text-black p-12 z-50 min-h-screen">
            <div className="flex justify-between items-start border-b-2 border-slate-200 pb-8 mb-8">
              <div>
                <h1 className="text-4xl font-black text-slate-900 tracking-tight">RK Trendz</h1>
                <p className="text-sm text-slate-500 mt-1">Network Marketing Platform</p>
                <div className="mt-4 text-sm text-slate-600"><p>123 Business Avenue, Tech Park</p><p>Mumbai, Maharashtra, 400001</p><p className="font-bold mt-1">GSTIN: <span className="font-mono text-slate-500">09XXXXX0000X1Z0</span> (Pending)</p></div>
              </div>
              <div className="text-right">
                <h2 className="text-3xl font-bold text-slate-300 uppercase tracking-widest">Tax Invoice</h2>
                <p className="font-mono text-lg text-slate-800 mt-2">#INV-{activeInvoice.order_id.toString().padStart(6, '0')}</p>
                <p className="text-sm text-slate-500 mt-1">Date: {new Date(activeInvoice.created_at).toLocaleDateString()}</p>
              </div>
            </div>

            <div className="mb-10">
              <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">Billed To</h3>
              <p className="text-lg font-bold text-slate-900">{user.full_name}</p>
              <p className="text-slate-600">{user.email}</p>
              <p className="text-slate-600 mt-1">User ID: <span className="font-mono">#{user.id}</span></p>
            </div>

            <table className="w-full text-left mb-10">
              <thead className="bg-slate-50 border-y border-slate-200">
                <tr><th className="py-3 px-4 text-sm font-bold text-slate-700">Description</th><th className="py-3 px-4 text-sm font-bold text-slate-700 text-center">Qty</th><th className="py-3 px-4 text-sm font-bold text-slate-700 text-right">Total Amount</th></tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                <tr>
                  <td className="py-4 px-4"><p className="font-bold text-slate-900">Digital Package: {activeInvoice.package_name}</p><p className="text-xs text-slate-500 mt-1">Platform activation & {activeInvoice.lucky_draw_coupons} Lucky Draw Coupons</p></td>
                  <td className="py-4 px-4 text-center text-slate-700">1</td>
                  <td className="py-4 px-4 text-right font-bold text-slate-900">₹{parseFloat(activeInvoice.amount).toLocaleString('en-IN')}</td>
                </tr>
              </tbody>
            </table>

            <div className="flex justify-end">
              <div className="w-1/2 border-t border-slate-200 pt-4">
                <div className="flex justify-between mb-2 text-sm text-slate-600"><span>Base Amount</span><span>₹{(parseFloat(activeInvoice.amount) / 1.18).toFixed(2)}</span></div>
                <div className="flex justify-between mb-4 text-sm text-slate-600"><span>IGST (18%)</span><span>₹{(parseFloat(activeInvoice.amount) - (parseFloat(activeInvoice.amount) / 1.18)).toFixed(2)}</span></div>
                <div className="flex justify-between items-center border-t-2 border-slate-800 pt-4"><span className="text-lg font-bold text-slate-900">Total Invoice Value</span><span className="text-2xl font-black text-slate-900">₹{parseFloat(activeInvoice.amount).toLocaleString('en-IN')}</span></div>
                <p className="text-right text-xs text-slate-400 mt-1">(Inclusive of all taxes)</p>
              </div>
            </div>

            <div className="mt-32 pt-8 border-t border-slate-200 text-center">
              <p className="text-sm font-bold text-slate-800">For RK Trendz</p><p className="text-xs text-slate-500 mt-1">Authorized Signatory</p><p className="text-xs text-slate-400 mt-8">This is a computer-generated invoice and does not require a physical signature.</p>
            </div>
          </div>
        )}
      </>
    );
  };

  // ---------------------------------------------------------
  // 7. REAL HELP & SUPPORT TAB
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
      <div className="max-w-5xl mx-auto space-y-6">
        <div className="mb-8 flex justify-between items-end">
          <div><h2 className="text-2xl font-bold text-slate-900">Help & Support</h2><p className="text-sm text-slate-500">Need assistance? Open a ticket to reach our admin team.</p></div>
          <button onClick={() => setIsTicketModalOpen(true)} className="flex items-center px-4 py-2 bg-slate-900 text-white font-bold rounded-md hover:bg-slate-800 transition-colors"><Plus className="h-4 w-4 mr-2" /> Open New Ticket</button>
        </div>

        <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-50 text-slate-500 font-medium border-b border-slate-200">
                <tr><th className="px-6 py-4">Ticket ID</th><th className="px-6 py-4">Subject</th><th className="px-6 py-4">Date Opened</th><th className="px-6 py-4 text-center">Status</th></tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {isLoading ? (
                  <tr><td colSpan="4" className="px-6 py-10 text-center text-slate-400"><Loader2 className="h-6 w-6 animate-spin mx-auto mb-2" /> Loading tickets...</td></tr>
                ) : tickets.length === 0 ? (
                  <tr><td colSpan="4" className="px-6 py-16 text-center text-slate-500"><MessageSquare className="h-12 w-12 text-slate-200 mx-auto mb-3" />You have no active support tickets.</td></tr>
                ) : (
                  tickets.map((ticket, idx) => (
                    <tr key={idx} className="hover:bg-slate-50 transition-colors">
                      <td className="px-6 py-4 font-mono text-slate-500 text-xs">#TKT-{ticket.id}</td>
                      <td className="px-6 py-4 text-slate-900 font-medium">{ticket.subject}</td>
                      <td className="px-6 py-4 text-slate-600 whitespace-nowrap">{new Date(ticket.created_at || ticket.date).toLocaleDateString()}</td>
                      <td className="px-6 py-4 text-center"><span className={`px-2.5 py-1 text-xs font-semibold rounded-full ${ticket.status === 'Open' ? 'bg-amber-100 text-amber-700' : 'bg-emerald-100 text-emerald-700'}`}>{ticket.status}</span></td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* CREATE TICKET MODAL */}
        {isTicketModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-in fade-in">
            <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md overflow-hidden animate-in zoom-in-95">
              <div className="px-6 py-4 border-b border-slate-100 flex justify-between items-center bg-slate-50"><h3 className="text-lg font-bold text-slate-900">Create Support Ticket</h3><button onClick={() => setIsTicketModalOpen(false)} className="text-slate-400 hover:text-slate-600"><X className="h-5 w-5" /></button></div>
              <div className="p-6 space-y-6">
                <form onSubmit={handleCreateTicket} className="space-y-4">
                  <div><label className="block text-sm font-semibold text-slate-700 mb-1">Subject</label><input type="text" required value={subject} onChange={(e) => setSubject(e.target.value)} placeholder="e.g. Missing Withdrawal" className="w-full px-4 py-3 bg-white border border-slate-300 rounded-lg text-slate-900 focus:ring-2 focus:ring-slate-900" /></div>
                  <div><label className="block text-sm font-semibold text-slate-700 mb-1">Message</label><textarea required rows="4" value={message} onChange={(e) => setMessage(e.target.value)} placeholder="Describe your issue in detail..." className="w-full px-4 py-3 bg-white border border-slate-300 rounded-lg text-slate-900 focus:ring-2 focus:ring-slate-900"></textarea></div>
                  <button type="submit" disabled={!subject || !message || isSubmitting} className="w-full py-3.5 px-4 bg-slate-900 hover:bg-slate-800 text-white font-bold rounded-lg shadow-md transition-all disabled:opacity-50 flex justify-center">
                    {isSubmitting ? <Loader2 className="h-5 w-5 animate-spin" /> : "Submit Ticket"}
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
    <div className="min-h-screen bg-slate-50 flex">
      <aside className="hidden md:flex flex-col w-64 bg-slate-900 text-slate-300 transition-all border-r border-slate-800 print:hidden">
        <div className="h-16 flex items-center px-6 border-b border-slate-800 bg-slate-950">
          <h1 className="text-xl font-extrabold text-white tracking-tight">RK <span className="text-emerald-500">Trendz</span></h1>
        </div>
        <div className="flex-1 overflow-y-auto py-4 px-3 space-y-1">
          {menuItems.map((item) => (
            <button
              key={item.name}
              onClick={() => switchTab(item.name)}
              className={`w-full flex items-center px-3 py-2.5 text-sm font-medium rounded-lg transition-all ${
                activeTab === item.name ? "bg-emerald-600 text-white shadow-md shadow-emerald-900/20" : "hover:bg-slate-800 hover:text-white"
              }`}
            >
              <item.icon className={`mr-3 h-5 w-5 ${activeTab === item.name ? "text-emerald-100" : "text-slate-400"}`} />
              {item.name}
            </button>
          ))}
        </div>
        <div className="p-4 border-t border-slate-800">
          <button onClick={logout} className="w-full flex items-center px-3 py-2.5 text-sm font-medium text-red-400 rounded-lg hover:bg-slate-800 hover:text-red-300 transition-all">
            <LogOut className="mr-3 h-5 w-5" /> Secure Logout
          </button>
        </div>
      </aside>

      <main className="flex-1 flex flex-col min-w-0 overflow-hidden bg-white md:bg-slate-50 print:bg-white print:m-0 print:p-0">
        <header className="h-16 flex items-center justify-between px-4 sm:px-6 lg:px-8 border-b border-slate-200 bg-white md:bg-transparent md:border-none shrink-0 print:hidden">
           <div className="flex items-center md:hidden"><h1 className="text-lg font-bold text-slate-900">RK <span className="text-emerald-500">Trendz</span></h1></div>
           <div className="ml-auto flex items-center gap-3">
              <button onClick={() => window.location.reload()} className="flex items-center px-3 py-1.5 text-sm font-semibold text-slate-600 bg-white border border-slate-200 rounded-md shadow-sm hover:bg-slate-50 hover:text-emerald-600 transition-all">
                 <RefreshCw className="h-4 w-4 sm:mr-2" /><span className="hidden sm:inline">Refresh Data</span>
              </button>
              <button onClick={logout} className="md:hidden p-2 text-slate-400 hover:text-red-500 bg-slate-50 rounded-md border border-slate-200"><LogOut className="h-5 w-5" /></button>
           </div>
        </header>

        <div className="flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8 print:p-0 print:overflow-visible">
          {activeTab === "Overview" && <OverviewTab />}
          {activeTab === "My Profile" && <ProfileTab />}
          {activeTab === "Wallet & Payouts" && <WalletTab />}
          {activeTab === "My Network Tree" && <NetworkTab />}
          {activeTab === "Product Catalog" && <ProductCatalogTab />}
          {activeTab === "My Orders & Invoices" && <OrdersTab />}
          {activeTab === "Help & Support" && <SupportTab />}
        </div>
      </main>
    </div>
  );
}
