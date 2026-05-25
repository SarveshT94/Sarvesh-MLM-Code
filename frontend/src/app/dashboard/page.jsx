"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import useAuthStore from "@/store/authStore";
import { useRouter } from "next/navigation";
import { requestProfileUpdate, verifyProfileOtp } from "@/services/profile";
import { fetchWalletData, submitWithdrawal, submitP2PTransfer } from "@/services/wallet";
import { fetchNetworkData, fetchUplineData } from "@/services/team";
import { fetchPackages, purchasePlan, fetchCompensationPlan, fetchUserOrders } from "@/services/package";
import { fetchUserRank } from "@/services/gamification";
import { fetchTickets, createTicket } from "@/services/support";
import { fetchKycData, submitKycData } from "@/services/kyc";
import {
  LayoutDashboard, UserCircle, Users, ShoppingBag,
  Wallet, LogOut, Share2, Copy, CheckCircle2, TrendingUp, Camera, ShieldCheck,
  AlertCircle, Loader2, GitMerge, UserPlus, X, Zap, Target, Globe,
  Download, Receipt, ArrowRightLeft, LifeBuoy, Award, MessageSquare, Image as ImageIcon,
  FileCheck, UploadCloud, ChevronRight, Building, MapPin, Mail, Phone, ListTree,
  Star, Heart, Rocket, Menu, ChevronDown
} from "lucide-react";

// ─── Premium Color Map ───────────────────────────────────────────
const COLOR_MAP = {
  emerald: { iconBg: "bg-emerald-50/80 border-emerald-200", icon: "text-emerald-700", btn: "text-emerald-700", tileBg: "bg-gradient-to-br from-emerald-50 to-white" },
  gold:    { iconBg: "bg-amber-50/80 border-amber-200", icon: "text-amber-700", btn: "text-amber-700", tileBg: "bg-gradient-to-br from-amber-50 to-white" },
  rose:    { iconBg: "bg-rose-50/80 border-rose-200", icon: "text-rose-700", btn: "text-rose-700", tileBg: "bg-gradient-to-br from-rose-50 to-white" },
  blue:    { iconBg: "bg-blue-50/80 border-blue-200", icon: "text-blue-700", btn: "text-blue-700", tileBg: "bg-gradient-to-br from-blue-50 to-white" },
  violet:  { iconBg: "bg-violet-50/80 border-violet-200", icon: "text-violet-700", btn: "text-violet-700", tileBg: "bg-gradient-to-br from-violet-50 to-white" },
  cyan:    { iconBg: "bg-cyan-50/80 border-cyan-200", icon: "text-cyan-700", btn: "text-cyan-700", tileBg: "bg-gradient-to-br from-cyan-50 to-white" },
};

export default function DashboardPage() {
  const { user, isAuthenticated, isChecking, logout, setAuth } = useAuthStore();
  const router = useRouter();
  const [activeTab, setActiveTab] = useState("Overview");
  const [copied, setCopied] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  useEffect(() => {
    if (!isChecking && !isAuthenticated) router.push("/login");
  }, [isAuthenticated, isChecking, router]);

  useEffect(() => {
    const savedTab = sessionStorage.getItem("dashboardTab");
    if (savedTab) setActiveTab(savedTab);
  }, []);

  const switchTab = useCallback((tabName) => {
    setActiveTab(tabName);
    sessionStorage.setItem("dashboardTab", tabName);
    setSidebarOpen(false);
  }, []);

  if (isChecking || !isAuthenticated || !user) return null;

  const refCode = user?.referral_code || "PENDING";
  const shareUrl = `${typeof window !== "undefined" ? window.location.origin : ""}/register?ref=${refCode}`;

  const handleShare = async () => {
    const shareData = {
      title: "Join my RK Trendz Network!",
      text: `Sign up using my referral code: ${refCode} and join my team!`,
      url: shareUrl,
    };
    try {
      if (navigator.share) await navigator.share(shareData);
      else handleCopy();
    } catch (err) {
      console.error("Error sharing:", err);
    }
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
    { name: "Product Catalog", icon: ShoppingBag },
    { name: "My Orders & Invoices", icon: Receipt },
    { name: "Help & Support", icon: LifeBuoy },
  ];

  // ─────────────────────────────────────────────────────────────────
  // TAB: OVERVIEW
  // ─────────────────────────────────────────────────────────────────
  const OverviewTab = () => {
    const [rankData, setRankData] = useState({
      current_rank: "—", next_rank: "—",
      current_volume: 0, next_rank_volume: 0, progress_percentage: 0,
    });
    const [isLoadingRank, setIsLoadingRank] = useState(true);

    useEffect(() => {
      const loadRank = async () => {
        try {
          const res = await fetchUserRank();
          if (res.success && res.data) setRankData(res.data);
        } catch (e) { /* API not ready yet */ }
        finally { setIsLoadingRank(false); }
      };
      loadRank();
    }, []);

    const quickCards = [
      { title: "Wallet Balance", value: "View Wallet", icon: Wallet, color: "emerald", tab: "Wallet & Payouts", btnText: "Manage Payouts" },
      { title: "Active Downline", value: "My Network", icon: Users, color: "gold", tab: "My Network Tree", btnText: "View Network Tree" },
      { title: "Current Plan", value: "Free Tier", icon: ShoppingBag, color: "rose", tab: "Product Catalog", btnText: "Upgrade Plan" },
      { title: "Referral Code", value: refCode, icon: Share2, color: "blue", tab: "Overview", btnText: "Copy Code" },
    ];

    return (
      <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
        {/* Welcome banner */}
        <div className="relative bg-gradient-to-br from-[#0f2a1f] via-[#1a3a2a] to-amber-900/40 rounded-2xl p-7 text-white overflow-hidden">
          <div className="absolute inset-0 opacity-5" style={{ backgroundImage: `url("data:image/svg+xml,%3Csvg width='40' height='40' viewBox='0 0 40 40' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='%23fff' fill-opacity='1'%3E%3Ccircle cx='20' cy='20' r='2'/%3E%3C/g%3E%3C/svg%3E")` }} />
          <div className="relative">
            <p className="text-amber-200/70 text-sm font-medium mb-1">Good day 👋</p>
            <h2 className="text-2xl font-bold text-white">{user.full_name.split(" ")[0]}</h2>
            <p className="text-amber-200/70 text-sm mt-1">Here's your network overview for today</p>
          </div>
          <Globe className="absolute -right-6 -bottom-6 h-40 w-40 text-white/5" />
        </div>

        {/* Rank progress card */}
        <div className="bg-white rounded-2xl border border-amber-100/50 shadow-sm p-6">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <div className="p-2.5 bg-amber-50 rounded-xl">
                <Award className="h-5 w-5 text-amber-600" />
              </div>
              <div>
                <p className="text-xs text-slate-400 font-semibold uppercase tracking-wider">Current Rank</p>
                <h3 className="text-lg font-bold text-slate-900">
                  {isLoadingRank ? <span className="text-slate-300">Loading…</span> : rankData.current_rank}
                </h3>
              </div>
            </div>
            {rankData.next_rank && rankData.next_rank !== "Max Rank Reached" && (
              <div className="flex items-center gap-1.5 bg-slate-50 border border-slate-200 rounded-xl px-3 py-2">
                <Target className="h-3.5 w-3.5 text-emerald-500" />
                <span className="text-xs font-semibold text-slate-600">Next: {rankData.next_rank}</span>
              </div>
            )}
          </div>
          <div className="w-full bg-slate-100 rounded-full h-2.5 overflow-hidden">
            <div
              className="bg-gradient-to-r from-amber-400 to-amber-600 h-full rounded-full transition-all duration-1000"
              style={{ width: `${rankData.progress_percentage}%` }}
            />
          </div>
          <div className="flex justify-between mt-2 text-xs font-semibold">
            <span className="text-amber-600">₹{rankData.current_volume.toLocaleString("en-IN")} vol.</span>
            <span className="text-slate-400">
              {rankData.next_rank !== "Max Rank Reached"
                ? `₹${rankData.next_rank_volume.toLocaleString("en-IN")} target`
                : "Maximum rank achieved!"}
            </span>
          </div>
        </div>

        {/* Premium tiles */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          {quickCards.map((card) => {
            const c = COLOR_MAP[card.color];
            return (
              <div key={card.title} className={`${c.tileBg} border border-slate-100 rounded-2xl shadow-sm group hover:shadow-md hover:-translate-y-0.5 transition-all duration-200`}>
                <div className="p-5">
                  <div className="flex items-center gap-4">
                    <div className={`p-3 rounded-xl border ${c.iconBg}`}>
                      <card.icon className={`h-5 w-5 ${c.icon}`} />
                    </div>
                    <div>
                      <p className="text-xs text-slate-500 font-medium">{card.title}</p>
                      <p className="text-base font-bold text-slate-900 mt-0.5">{card.value}</p>
                    </div>
                  </div>
                </div>
                <div className="border-t border-slate-100/60 px-5 py-3">
                  <button onClick={() => switchTab(card.tab)} className={`text-xs font-bold flex items-center justify-between w-full ${c.btn} transition-colors`}>
                    {card.btnText} <ChevronRight className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
            );
          })}
        </div>

        {/* Referral card */}
        <div className="bg-white rounded-2xl border border-amber-100/50 shadow-sm p-6">
          <h3 className="font-bold text-slate-900 mb-1">Grow Your Network</h3>
          <p className="text-sm text-slate-500 mb-5">Share your referral link and earn commissions when your network activates.</p>
          <div className="flex flex-col sm:flex-row gap-3">
            <div className="flex-1 bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 flex items-center justify-between">
              <div>
                <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-0.5">Your Code</p>
                <p className="text-lg font-bold text-amber-600 tracking-widest">{refCode}</p>
              </div>
              <button
                onClick={handleCopy}
                disabled={refCode === "PENDING"}
                className="p-2 bg-white border border-slate-200 rounded-lg hover:bg-amber-50 hover:text-amber-600 hover:border-amber-200 transition-all text-slate-500 disabled:opacity-40"
              >
                {copied ? <CheckCircle2 className="h-4 w-4 text-amber-500" /> : <Copy className="h-4 w-4" />}
              </button>
            </div>
            <button
              onClick={handleShare}
              disabled={refCode === "PENDING"}
              className="flex items-center justify-center gap-2 px-6 py-3 bg-[#0f2a1f] hover:bg-[#1a3a2a] text-white font-semibold rounded-xl shadow-sm transition-all disabled:opacity-40 text-sm"
            >
              <Share2 className="h-4 w-4" /> Share Link
            </button>
          </div>
        </div>
      </div>
    );
  };

  // ─────────────────────────────────────────────────────────────────
  // TAB: COMPANY INFO
  // ─────────────────────────────────────────────────────────────────
  const CompanyInfoTab = () => {
    const values = [
      { icon: ShieldCheck, color: "text-emerald-600", bg: "bg-emerald-50", title: "Transparent & Compliant", desc: "Fully registered under Indian corporate law with clear earning disclosures on every plan." },
      { icon: Star, color: "text-amber-500", bg: "bg-amber-50", title: "Member-First Culture", desc: "Every policy, payout structure, and product is designed to ensure our members thrive." },
      { icon: Heart, color: "text-rose-500", bg: "bg-rose-50", title: "Community Driven", desc: "We believe in building lasting relationships, not just transactions." },
      { icon: Rocket, color: "text-indigo-600", bg: "bg-indigo-50", title: "Growth Oriented", desc: "Continuous product updates, rank upgrades, and new earning opportunities every quarter." },
    ];

    return (
      <div className="max-w-5xl mx-auto space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
        {/* Hero banner */}
        <div className="relative bg-gradient-to-br from-[#0f2a1f] to-[#1a3a2a] rounded-2xl p-8 text-white overflow-hidden">
          <div className="absolute inset-0 opacity-10" style={{ backgroundImage: `url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='%23fff' fill-opacity='1'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/svg%3E")` }} />
          <div className="relative">
            <div className="inline-flex items-center gap-2 bg-amber-500/20 rounded-full px-4 py-1.5 text-xs font-bold uppercase tracking-wider mb-4">
              <Building className="h-3.5 w-3.5" /> Registered Company
            </div>
            <h2 className="text-3xl font-black tracking-tight">RK Trendz Pvt. Ltd.</h2>
            <p className="text-amber-200/70 mt-2 text-sm leading-relaxed max-w-2xl">
              A premier Direct Selling and Network Marketing platform empowering individuals through world-class digital products and transparent earning opportunities — fully compliant with Indian MLM regulations.
            </p>
          </div>
          <Building className="absolute -right-8 -bottom-8 h-48 w-48 text-white/10" />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-6">
            {/* Legal Identity */}
            <div className="bg-white rounded-2xl border border-amber-100/50 shadow-sm p-6">
              <h3 className="font-bold text-slate-900 mb-1 flex items-center gap-2">
                <ShieldCheck className="h-5 w-5 text-emerald-500" /> Legal Identity
              </h3>
              <p className="text-xs text-slate-400 mb-5">
                Displaying our CIN and GSTIN is mandated for trust and compliance under Indian Direct Selling Guidelines, 2021.
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="bg-slate-50 rounded-xl border border-slate-100 p-4">
                  <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1.5">CIN (Ministry of Corporate Affairs)</p>
                  <p className="text-sm font-mono font-bold text-slate-800">U72900MH2024PTC000000</p>
                </div>
                <div className="bg-slate-50 rounded-xl border border-slate-100 p-4">
                  <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1.5">GSTIN (GST Registration)</p>
                  <p className="text-sm font-mono font-bold text-slate-800">27AAACR0000A1Z5</p>
                </div>
              </div>
            </div>

            {/* Contact */}
            <div className="bg-white rounded-2xl border border-amber-100/50 shadow-sm p-6">
              <h3 className="font-bold text-slate-900 mb-5">Contact & Support</h3>
              <div className="space-y-4">
                {[
                  { icon: MapPin, color: "bg-indigo-50 text-indigo-600", label: "Head Office", detail: "101, Business Park Tower A, Andheri East, Mumbai, Maharashtra 400069" },
                  { icon: Mail, color: "bg-emerald-50 text-emerald-600", label: "Email Support", detail: "support@rktrendz.com" },
                  { icon: Phone, color: "bg-amber-50 text-amber-600", label: "Helpline", detail: "+91 1800-123-4567 (Mon–Sat, 10 AM – 6 PM)" },
                ].map((item) => (
                  <div key={item.label} className="flex items-start gap-4">
                    <div className={`p-2.5 rounded-xl ${item.color} shrink-0`}>
                      <item.icon className="h-4 w-4" />
                    </div>
                    <div>
                      <p className="text-xs font-bold text-slate-500 uppercase tracking-wider">{item.label}</p>
                      <p className="text-sm text-slate-700 mt-0.5 leading-relaxed">{item.detail}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Values */}
            <div className="bg-white rounded-2xl border border-amber-100/50 shadow-sm p-6">
              <h3 className="font-bold text-slate-900 mb-5">Our Core Values</h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {values.map((v) => (
                  <div key={v.title} className="flex items-start gap-3 p-4 bg-slate-50 rounded-xl border border-slate-100">
                    <div className={`p-2 rounded-lg ${v.bg} shrink-0`}>
                      <v.icon className={`h-4 w-4 ${v.color}`} />
                    </div>
                    <div>
                      <p className="text-sm font-bold text-slate-800">{v.title}</p>
                      <p className="text-xs text-slate-500 mt-0.5 leading-relaxed">{v.desc}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="space-y-6">
            {/* Documents */}
            <div className="bg-[#0f2a1f] rounded-2xl border border-[#1a3a2a] p-6 text-white">
              <h3 className="font-bold mb-1 flex items-center gap-2">
                <Download className="h-4 w-4 text-amber-400" /> Documents
              </h3>
              <p className="text-amber-200/60 text-xs mb-5 leading-relaxed">
                Download our publicly available documents for your reference.
              </p>
              <div className="space-y-2">
                {[
                  "Certificate of Incorporation",
                  "Terms & Conditions",
                  "Income Disclosure Statement",
                  "Privacy Policy",
                ].map((doc) => (
                  <button
                    key={doc}
                    className="w-full flex items-center justify-between p-3.5 bg-white/10 hover:bg-white/20 border border-white/10 rounded-xl transition-all text-sm font-medium"
                  >
                    {doc} <Download className="h-3.5 w-3.5 text-amber-200/50" />
                  </button>
                ))}
              </div>
              <p className="text-[10px] text-amber-200/40 mt-4 leading-relaxed">
                Note: Internal documents such as the GST certificate are not distributed to members per company policy.
              </p>
            </div>

            {/* Support CTA */}
            <div className="bg-amber-50 border border-amber-100 rounded-2xl p-6 text-center">
              <div className="w-12 h-12 bg-white rounded-xl flex items-center justify-center shadow-sm mx-auto mb-3 border border-amber-100">
                <LifeBuoy className="h-6 w-6 text-amber-600" />
              </div>
              <h4 className="font-bold text-slate-900 mb-1">Need Help?</h4>
              <p className="text-xs text-slate-500 mb-4 leading-relaxed">Our support team is ready to assist you.</p>
              <button
                onClick={() => switchTab("Help & Support")}
                className="w-full py-2.5 bg-amber-600 hover:bg-amber-700 text-white font-semibold rounded-xl text-sm transition-all"
              >
                Open a Support Ticket
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  };

  // ─────────────────────────────────────────────────────────────────
  // TAB: PROFILE (unchanged except color inheritance)
  // ─────────────────────────────────────────────────────────────────
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
        try {
          const rankRes = await fetchUserRank();
          if (rankRes.success && rankRes.data) setUserRank(rankRes.data.current_rank);
        } catch (e) { /* backend not ready */ }
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
      setStatus({ type: "", msg: "" });
      setIsLoading(true);
      const newIdentifier = type === "email" ? form.email : form.phone;
      try {
        const res = await requestProfileUpdate(type, newIdentifier);
        if (res.success) { setStatus({ type: "success", msg: res.data.message }); setActiveVerification(type); }
        else { setStatus({ type: "error", msg: res.message }); }
      } catch (e) { setStatus({ type: "error", msg: "Request failed. Please try again." }); }
      setIsLoading(false);
    };

    const handleVerifyOtp = async () => {
      if (otpCode.length !== 6) return setStatus({ type: "error", msg: "Please enter a valid 6-digit OTP." });
      setIsLoading(true);
      setStatus({ type: "", msg: "" });
      try {
        const res = await verifyProfileOtp(otpCode);
        if (res.success) {
          setStatus({ type: "success", msg: res.data.message });
          setAuth({ ...user, [activeVerification]: form[activeVerification] });
          setActiveVerification(null);
          setOtpCode("");
        } else { setStatus({ type: "error", msg: res.message }); }
      } catch (e) { setStatus({ type: "error", msg: "Verification failed. Please try again." }); }
      setIsLoading(false);
    };

    const saveGeneralDetails = async (e) => {
      e.preventDefault();
      setStatus({ type: "success", msg: "Profile information saved. (Backend integration pending)" });
      setTimeout(() => setStatus({ type: "", msg: "" }), 3000);
    };

    return (
      <div className="max-w-5xl mx-auto space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
        {status.msg && (
          <div className={`p-4 rounded-xl flex items-center gap-3 border-l-4 ${status.type === "error" ? "bg-red-50 border-red-500 text-red-700" : "bg-emerald-50 border-emerald-500 text-emerald-700"}`}>
            {status.type === "error" ? <AlertCircle className="h-5 w-5 shrink-0" /> : <CheckCircle2 className="h-5 w-5 shrink-0" />}
            <p className="text-sm font-semibold">{status.msg}</p>
          </div>
        )}
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
          <div className="xl:col-span-1 space-y-6">
            {/* Avatar card */}
            <div className="bg-white rounded-2xl border border-amber-100/50 shadow-sm p-6 text-center">
              <div
                className="relative inline-block mb-4 group cursor-pointer"
                onClick={() => fileInputRef.current?.click()}
              >
                <div className="h-28 w-28 rounded-full overflow-hidden border-4 border-white ring-2 ring-amber-100 shadow-lg">
                  {photoPreview
                    ? <img src={photoPreview} alt="Profile" className="h-full w-full object-cover" />
                    : <div className="h-full w-full flex items-center justify-center bg-gradient-to-br from-amber-100 to-amber-200 text-amber-700 text-4xl font-black">{user.full_name.charAt(0).toUpperCase()}</div>
                  }
                </div>
                <div className="absolute inset-0 bg-slate-900/40 rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
                  <Camera className="h-7 w-7 text-white" />
                </div>
                <input type="file" ref={fileInputRef} onChange={handlePhotoChange} accept="image/*" className="hidden" />
              </div>
              <h3 className="font-bold text-slate-900">{user.full_name}</h3>
              <p className="text-xs text-slate-400 mt-0.5">{user.email}</p>
              <span className="inline-flex items-center gap-1.5 mt-3 px-3 py-1.5 bg-amber-50 text-amber-700 rounded-full text-xs font-bold border border-amber-100">
                <Award className="h-3.5 w-3.5" /> {userRank}
              </span>
            </div>

            {/* Account security */}
            <div className="bg-white rounded-2xl border border-amber-100/50 shadow-sm overflow-hidden">
              <div className="px-5 py-4 border-b border-amber-100/50 bg-amber-50/30">
                <h3 className="text-sm font-bold text-slate-700 flex items-center gap-2">
                  <ShieldCheck className="h-4 w-4 text-slate-400" /> Account Security
                </h3>
              </div>
              <div className="p-5 space-y-5">
                {[
                  { label: "Email Address", field: "email", type: "email", check: isEmailChanged, verKey: "email" },
                  { label: "Phone Number", field: "phone", type: "text", check: isPhoneChanged, verKey: "phone" },
                ].map((f) => (
                  <div key={f.field} className="space-y-2">
                    <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">{f.label}</label>
                    <div className="flex gap-2">
                      <input
                        type={f.type}
                        value={form[f.field]}
                        disabled={activeVerification === f.verKey}
                        onChange={(e) => setForm({ ...form, [f.field]: e.target.value })}
                        className="flex-1 px-3 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm font-medium focus:ring-2 focus:ring-amber-500 outline-none"
                      />
                      <button
                        onClick={() => handleRequestOtp(f.verKey)}
                        disabled={!f.check || isLoading || activeVerification === f.verKey}
                        className="px-4 py-2.5 bg-[#0f2a1f] hover:bg-[#1a3a2a] text-white text-xs font-bold rounded-xl transition-all disabled:opacity-40 disabled:bg-slate-100 disabled:text-slate-400"
                      >
                        Update
                      </button>
                    </div>
                    {activeVerification === f.verKey && (
                      <div className="flex gap-2 mt-1">
                        <input
                          type="text" maxLength="6" placeholder="6-digit OTP"
                          value={otpCode} onChange={(e) => setOtpCode(e.target.value)}
                          className="flex-1 px-3 py-2.5 text-center font-mono text-sm border border-slate-200 rounded-xl focus:ring-2 focus:ring-amber-500 outline-none"
                        />
                        <button onClick={handleVerifyOtp} className="px-4 bg-amber-600 hover:bg-amber-700 text-white text-xs font-bold rounded-xl transition-colors">
                          Verify
                        </button>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Personal & family form */}
          <div className="xl:col-span-2">
            <form onSubmit={saveGeneralDetails} className="bg-white rounded-2xl border border-amber-100/50 shadow-sm overflow-hidden">
              <div className="px-6 py-4 border-b border-amber-100/50 bg-amber-50/30 flex items-center justify-between">
                <h3 className="font-bold text-slate-900">Personal & Family Details</h3>
                <span className="text-[10px] font-bold bg-slate-200 text-slate-600 px-2.5 py-1 rounded-full uppercase tracking-wider">Optional</span>
              </div>
              <div className="p-6 space-y-8">
                <div className="space-y-4">
                  <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider border-b border-slate-100 pb-2">General Information</h4>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-semibold text-slate-700 mb-1.5">Date of Birth</label>
                      <input type="date" value={personalForm.dob} onChange={(e) => setPersonalForm({ ...personalForm, dob: e.target.value })} className="w-full px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm font-medium focus:ring-2 focus:ring-slate-900 outline-none" />
                    </div>
                    <div>
                      <label className="block text-sm font-semibold text-slate-700 mb-1.5">Gender</label>
                      <select value={personalForm.gender} onChange={(e) => setPersonalForm({ ...personalForm, gender: e.target.value })} className="w-full px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm font-medium focus:ring-2 focus:ring-slate-900 outline-none">
                        <option value="male">Male</option>
                        <option value="female">Female</option>
                        <option value="other">Other</option>
                      </select>
                    </div>
                    <div className="md:col-span-2">
                      <label className="block text-sm font-semibold text-slate-700 mb-1.5">Full Address</label>
                      <input type="text" placeholder="Street, Landmark, Area" value={personalForm.address} onChange={(e) => setPersonalForm({ ...personalForm, address: e.target.value })} className="w-full px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm font-medium focus:ring-2 focus:ring-slate-900 outline-none" />
                    </div>
                    <div>
                      <label className="block text-sm font-semibold text-slate-700 mb-1.5">City / District</label>
                      <input type="text" placeholder="City" value={personalForm.city} onChange={(e) => setPersonalForm({ ...personalForm, city: e.target.value })} className="w-full px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm font-medium focus:ring-2 focus:ring-slate-900 outline-none" />
                    </div>
                    <div className="flex gap-3">
                      <div className="flex-1">
                        <label className="block text-sm font-semibold text-slate-700 mb-1.5">State</label>
                        <input type="text" placeholder="State" value={personalForm.state} onChange={(e) => setPersonalForm({ ...personalForm, state: e.target.value })} className="w-full px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm font-medium focus:ring-2 focus:ring-slate-900 outline-none" />
                      </div>
                      <div className="w-1/3">
                        <label className="block text-sm font-semibold text-slate-700 mb-1.5">PIN Code</label>
                        <input type="text" placeholder="000000" value={personalForm.pincode} onChange={(e) => setPersonalForm({ ...personalForm, pincode: e.target.value })} className="w-full px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm font-medium focus:ring-2 focus:ring-slate-900 outline-none" />
                      </div>
                    </div>
                  </div>
                </div>
                <div className="space-y-4">
                  <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider border-b border-slate-100 pb-2">Nominee Details</h4>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-semibold text-slate-700 mb-1.5">Nominee Full Name</label>
                      <input type="text" placeholder="Name" value={familyForm.nomineeName} onChange={(e) => setFamilyForm({ ...familyForm, nomineeName: e.target.value })} className="w-full px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm font-medium focus:ring-2 focus:ring-slate-900 outline-none" />
                    </div>
                    <div>
                      <label className="block text-sm font-semibold text-slate-700 mb-1.5">Relation to User</label>
                      <input type="text" placeholder="e.g. Spouse, Child, Parent" value={familyForm.nomineeRelation} onChange={(e) => setFamilyForm({ ...familyForm, nomineeRelation: e.target.value })} className="w-full px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm font-medium focus:ring-2 focus:ring-slate-900 outline-none" />
                    </div>
                  </div>
                </div>
                <div className="border-t border-slate-100 pt-5">
                  <button type="submit" className="px-8 py-3 bg-[#0f2a1f] hover:bg-[#1a3a2a] text-white font-semibold rounded-xl shadow-sm transition-all text-sm hover:-translate-y-0.5">
                    Save Profile Information
                  </button>
                </div>
              </div>
            </form>
          </div>
        </div>
      </div>
    );
  };

  // ─────────────────────────────────────────────────────────────────
  // TAB: KYC (unchanged except color inheritance)
  // ─────────────────────────────────────────────────────────────────
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
      "IndusInd Bank", "Yes Bank", "IDFC First Bank", "Other",
    ];

    useEffect(() => {
      const loadKyc = async () => {
        setIsLoading(true);
        try {
          const res = await fetchKycData();
          if (res.success && res.data) {
            setKycData(res.data);
            setForm({
              pan_number: res.data.pan_number || "",
              aadhar_number: res.data.aadhar_number || "",
              bank_name: res.data.bank_name || "",
              bank_account_no: res.data.bank_account_no || "",
              bank_ifsc: res.data.bank_ifsc || "",
            });
          }
        } catch (e) { /* API pending */ }
        setIsLoading(false);
      };
      loadKyc();
    }, []);

    const handleFileChange = (e, key) => {
      setFiles((prev) => ({ ...prev, [key]: e.target.files[0] }));
    };

    const handleSubmit = async (e) => {
      e.preventDefault();
      setIsSubmitting(true);
      setStatusMsg({ type: "", msg: "" });
      try {
        const formData = new FormData();
        Object.entries(form).forEach(([key, val]) => formData.append(key, val));
        Object.entries(files).forEach(([key, file]) => { if (file) formData.append(key, file); });
        const res = await submitKycData(formData);
        if (res.success) {
          setStatusMsg({ type: "success", msg: "KYC documents submitted for verification." });
          const updated = await fetchKycData();
          if (updated.success) setKycData(updated.data);
        } else {
          setStatusMsg({ type: "error", msg: res.message });
        }
      } catch (e) {
        setStatusMsg({ type: "error", msg: "Submission failed. Please try again." });
      }
      setIsSubmitting(false);
    };

    const isLocked = kycData?.kyc_status === "pending" || kycData?.kyc_status === "approved";

    const FileBox = ({ label, keyName }) => (
      <div className={`relative border-2 border-dashed rounded-xl p-5 flex flex-col items-center justify-center text-center transition-all
        ${files[keyName] ? "border-amber-400 bg-amber-50" : "border-slate-200 hover:border-slate-300 bg-slate-50"}
        ${isLocked ? "opacity-50 pointer-events-none" : "cursor-pointer"}`}>
        <input
          type="file" disabled={isLocked}
          onChange={(e) => handleFileChange(e, keyName)}
          accept="image/*,.pdf"
          className="absolute inset-0 w-full h-full opacity-0 cursor-pointer disabled:cursor-not-allowed"
        />
        {files[keyName] ? (
          <>
            <CheckCircle2 className="h-7 w-7 text-amber-500 mb-1.5" />
            <p className="text-xs font-semibold text-amber-700 break-all">{files[keyName].name}</p>
          </>
        ) : (
          <>
            <UploadCloud className="h-7 w-7 text-slate-300 mb-1.5" />
            <p className="text-xs font-bold text-slate-600">{label}</p>
            <p className="text-[10px] text-slate-400 mt-0.5">Click or drag</p>
          </>
        )}
      </div>
    );

    const statusStyles = {
      approved: "bg-emerald-50 border-emerald-100 text-emerald-800",
      pending: "bg-amber-50 border-amber-100 text-amber-800",
      rejected: "bg-red-50 border-red-100 text-red-800",
      default: "bg-slate-50 border-slate-100 text-slate-700",
    };

    return (
      <div className="max-w-4xl mx-auto space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
        <div>
          <h2 className="text-2xl font-black text-slate-900">KYC Verification</h2>
          <p className="text-slate-500 text-sm mt-1">Submit your identity and banking documents to unlock withdrawals.</p>
        </div>
        {isLoading ? (
          <div className="flex justify-center py-20"><Loader2 className="h-8 w-8 animate-spin text-amber-500" /></div>
        ) : (
          <div className="bg-white rounded-2xl border border-amber-100/50 shadow-sm overflow-hidden">
            <div className={`p-5 border-b flex items-center gap-4 ${statusStyles[kycData?.kyc_status] || statusStyles.default}`}>
              <ShieldCheck className="h-8 w-8 shrink-0" />
              <div>
                <p className="text-xs font-bold uppercase tracking-wider opacity-70">Verification Status</p>
                <p className="font-black text-xl capitalize">{kycData?.kyc_status || "Not Submitted"}</p>
                {kycData?.kyc_status === "rejected" && (
                  <p className="text-sm mt-1 font-semibold text-red-600">Reason: {kycData.kyc_rejection_reason}</p>
                )}
              </div>
            </div>

            <div className="p-6 md:p-8">
              {statusMsg.msg && (
                <div className={`p-4 rounded-xl mb-6 flex items-center gap-3 border ${statusMsg.type === "error" ? "bg-red-50 border-red-200 text-red-700" : "bg-emerald-50 border-emerald-200 text-emerald-700"}`}>
                  <AlertCircle className="h-5 w-5 shrink-0" />
                  <p className="text-sm font-semibold">{statusMsg.msg}</p>
                </div>
              )}
              <form onSubmit={handleSubmit} className="space-y-10">
                {/* Identity */}
                <div className="space-y-5">
                  <h3 className="font-bold text-slate-900 flex items-center gap-2 border-b border-slate-100 pb-3">
                    <UserCircle className="h-5 w-5 text-indigo-500" /> Identity Documents
                  </h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                    <div>
                      <label className="block text-sm font-semibold text-slate-700 mb-1.5">PAN Card Number</label>
                      <input
                        type="text" required disabled={isLocked}
                        value={form.pan_number}
                        onChange={(e) => setForm({ ...form, pan_number: e.target.value.toUpperCase() })}
                        placeholder="ABCDE1234F"
                        className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl text-sm font-medium focus:ring-2 focus:ring-indigo-500 outline-none"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-semibold text-slate-700 mb-1.5">Aadhaar Card Number</label>
                      <input
                        type="text" required disabled={isLocked}
                        value={form.aadhar_number}
                        onChange={(e) => setForm({ ...form, aadhar_number: e.target.value.replace(/\D/g, "") })}
                        maxLength="12" placeholder="XXXX XXXX XXXX"
                        className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl text-sm font-medium focus:ring-2 focus:ring-indigo-500 outline-none"
                      />
                    </div>
                  </div>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                    <FileBox label="Self Photo" keyName="photo" />
                    <FileBox label="PAN Card" keyName="pan" />
                    <FileBox label="Aadhaar Front" keyName="aadhar_front" />
                    <FileBox label="Aadhaar Back" keyName="aadhar_back" />
                  </div>
                </div>

                {/* Bank details */}
                <div className="space-y-5">
                  <h3 className="font-bold text-slate-900 flex items-center gap-2 border-b border-slate-100 pb-3">
                    <Wallet className="h-5 w-5 text-emerald-500" /> Payout Bank Details
                  </h3>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
                    <div>
                      <label className="block text-sm font-semibold text-slate-700 mb-1.5">Bank Name</label>
                      <select
                        required disabled={isLocked}
                        value={form.bank_name}
                        onChange={(e) => setForm({ ...form, bank_name: e.target.value })}
                        className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl text-sm font-medium focus:ring-2 focus:ring-emerald-500 outline-none"
                      >
                        <option value="" disabled>Select bank</option>
                        {indianBanks.map((b) => <option key={b} value={b}>{b}</option>)}
                      </select>
                    </div>
                    <div>
                      <label className="block text-sm font-semibold text-slate-700 mb-1.5">Account Number</label>
                      <input
                        type="text" required disabled={isLocked}
                        value={form.bank_account_no}
                        onChange={(e) => setForm({ ...form, bank_account_no: e.target.value.replace(/\D/g, "") })}
                        placeholder="Account Number"
                        className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl text-sm font-medium focus:ring-2 focus:ring-emerald-500 outline-none"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-semibold text-slate-700 mb-1.5">IFSC Code</label>
                      <input
                        type="text" required disabled={isLocked}
                        value={form.bank_ifsc}
                        onChange={(e) => setForm({ ...form, bank_ifsc: e.target.value.toUpperCase() })}
                        placeholder="HDFC0001234"
                        className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl text-sm font-medium focus:ring-2 focus:ring-emerald-500 outline-none"
                      />
                    </div>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <FileBox label="Bank Passbook / Cheque" keyName="bank_proof" />
                    <FileBox label="Digital Signature" keyName="signature" />
                  </div>
                </div>

                {!isLocked && (
                  <button
                    type="submit" disabled={isSubmitting}
                    className="w-full py-4 bg-[#0f2a1f] hover:bg-[#1a3a2a] text-white font-bold rounded-xl shadow-sm transition-all flex items-center justify-center gap-2 hover:-translate-y-0.5"
                  >
                    {isSubmitting ? <Loader2 className="h-5 w-5 animate-spin" /> : "Submit for Verification"}
                  </button>
                )}
              </form>
            </div>
          </div>
        )}
      </div>
    );
  };

  // ─────────────────────────────────────────────────────────────────
  // TAB: WALLET (unchanged except color inheritance)
  // ─────────────────────────────────────────────────────────────────
  const WalletTab = () => {
    const [balance, setBalance] = useState(0);
    const [transactions, setTransactions] = useState([]);
    const [isLoading, setIsLoading] = useState(true);
    const [isWithdrawOpen, setIsWithdrawOpen] = useState(false);
    const [withdrawAmount, setWithdrawAmount] = useState("");
    const [payoutMethod, setPayoutMethod] = useState("upi");
    const [payoutDetails, setPayoutDetails] = useState({ upiId: "", upiMobile: "", bankAccount: "", bankIfsc: "" });
    const [withdrawStatus, setWithdrawStatus] = useState({ type: "", msg: "" });
    const [isWithdrawing, setIsWithdrawing] = useState(false);
    const [isTransferOpen, setIsTransferOpen] = useState(false);
    const [transferReceiver, setTransferReceiver] = useState("");
    const [transferAmount, setTransferAmount] = useState("");
    const [transferStatus, setTransferStatus] = useState({ type: "", msg: "" });
    const [isTransferring, setIsTransferring] = useState(false);
    const [selectedTx, setSelectedTx] = useState(null);

    const loadWallet = useCallback(async () => {
      setIsLoading(true);
      try {
        const res = await fetchWalletData();
        if (res.success) { setBalance(res.balance); setTransactions(res.history); }
      } catch (e) { /* API pending */ }
      setIsLoading(false);
    }, []);

    useEffect(() => { loadWallet(); }, [loadWallet]);

    const handleWithdraw = async (e) => {
      e.preventDefault();
      setWithdrawStatus({ type: "", msg: "" });
      const amount = parseFloat(withdrawAmount);
      if (!amount || amount <= 0) return setWithdrawStatus({ type: "error", msg: "Enter a valid amount." });
      if (amount > balance) return setWithdrawStatus({ type: "error", msg: "Insufficient balance." });
      if (payoutMethod === "upi" && (!payoutDetails.upiId || !payoutDetails.upiMobile))
        return setWithdrawStatus({ type: "error", msg: "Fill in all UPI details." });
      if (payoutMethod === "bank" && (!payoutDetails.bankAccount || !payoutDetails.bankIfsc))
        return setWithdrawStatus({ type: "error", msg: "Fill in all bank details." });
      setIsWithdrawing(true);
      try {
        const res = await submitWithdrawal(amount, payoutMethod, payoutDetails);
        if (res.success) {
          setWithdrawStatus({ type: "success", msg: res.message });
          setWithdrawAmount("");
          await loadWallet();
          setTimeout(() => { setIsWithdrawOpen(false); setWithdrawStatus({ type: "", msg: "" }); }, 2000);
        } else { setWithdrawStatus({ type: "error", msg: res.message }); }
      } catch (e) { setWithdrawStatus({ type: "error", msg: "Request failed. Please try again." }); }
      setIsWithdrawing(false);
    };

    const handleTransfer = async (e) => {
      e.preventDefault();
      setTransferStatus({ type: "", msg: "" });
      const amount = parseFloat(transferAmount);
      if (!transferReceiver) return setTransferStatus({ type: "error", msg: "Enter a valid User ID or Email." });
      if (!amount || amount <= 0) return setTransferStatus({ type: "error", msg: "Enter a valid amount." });
      if (amount > balance) return setTransferStatus({ type: "error", msg: "Insufficient balance." });
      setIsTransferring(true);
      try {
        const res = await submitP2PTransfer(transferReceiver, amount);
        if (res.success) {
          setTransferStatus({ type: "success", msg: res.message });
          setTransferAmount(""); setTransferReceiver("");
          await loadWallet();
          setTimeout(() => { setIsTransferOpen(false); setTransferStatus({ type: "", msg: "" }); }, 2000);
        } else { setTransferStatus({ type: "error", msg: res.message }); }
      } catch (e) { setTransferStatus({ type: "error", msg: "Transfer failed. Please try again." }); }
      setIsTransferring(false);
    };

    const ModalWrapper = ({ open, onClose, children }) => !open ? null : (
      <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-in fade-in">
        <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md overflow-hidden animate-in slide-in-from-bottom-4 sm:zoom-in-95 max-h-[90vh] flex flex-col">
          {children}
        </div>
      </div>
    );

    const StatusAlert = ({ status }) => status.msg ? (
      <div className={`p-3.5 rounded-xl flex items-start gap-3 border ${status.type === "error" ? "bg-red-50 border-red-200 text-red-700" : "bg-emerald-50 border-emerald-200 text-emerald-700"}`}>
        <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
        <p className="text-sm font-semibold">{status.msg}</p>
      </div>
    ) : null;

    return (
      <div className="max-w-5xl mx-auto space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
        <div>
          <h2 className="text-2xl font-black text-slate-900">Wallet & Earnings</h2>
          <p className="text-slate-500 text-sm mt-1">Manage commissions, request payouts, and transfer funds.</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          {/* Balance card – premium gold/emerald gradient */}
          <div className="md:col-span-2 bg-gradient-to-br from-[#0f2a1f] to-amber-900/80 rounded-2xl p-6 text-white relative overflow-hidden">
            <p className="text-amber-200/70 text-xs font-bold uppercase tracking-widest mb-1 flex items-center gap-1.5">
              <Wallet className="h-3.5 w-3.5" /> Available Balance
            </p>
            <h3 className="text-4xl font-black tracking-tight mb-6">
              ₹{isLoading ? "—" : parseFloat(balance).toLocaleString("en-IN", { minimumFractionDigits: 2 })}
            </h3>
            <div className="flex flex-wrap gap-3">
              <button onClick={() => setIsWithdrawOpen(true)} className="px-5 py-2.5 bg-white text-[#0f2a1f] hover:bg-slate-50 text-sm font-bold rounded-xl shadow transition-all flex items-center gap-2 hover:-translate-y-0.5">
                <TrendingUp className="h-4 w-4" /> Request Payout
              </button>
              <button onClick={() => setIsTransferOpen(true)} className="px-5 py-2.5 bg-white/15 hover:bg-white/25 text-white border border-white/20 text-sm font-semibold rounded-xl transition-all flex items-center gap-2 hover:-translate-y-0.5">
                <ArrowRightLeft className="h-4 w-4" /> P2P Transfer
              </button>
            </div>
            <Wallet className="absolute -bottom-8 -right-8 h-40 w-40 text-white/5" />
          </div>

          <div className="bg-white border border-amber-100/50 rounded-2xl p-6 flex flex-col items-center justify-center text-center shadow-sm">
            <div className="p-3 bg-amber-50 text-amber-600 rounded-xl mb-3">
              <ArrowRightLeft className="h-6 w-6" />
            </div>
            <h4 className="font-bold text-slate-900 text-sm">Zero-Fee P2P</h4>
            <p className="text-xs text-slate-400 mt-1.5 leading-relaxed">Send funds instantly to any network member using their ID or email.</p>
          </div>
        </div>

        {/* Transaction ledger */}
        <div className="bg-white rounded-2xl border border-amber-100/50 shadow-sm overflow-hidden">
          <div className="px-6 py-4 border-b border-amber-100/50 bg-amber-50/30 flex items-center justify-between">
            <h3 className="font-bold text-slate-900">Transaction Ledger</h3>
            <button onClick={loadWallet} className="p-1.5 text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded-lg transition-all">
              <Zap className="h-4 w-4" />
            </button>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-50 text-slate-400 font-semibold border-b border-slate-100 text-xs uppercase tracking-wider">
                <tr>
                  <th className="px-6 py-3">Date</th>
                  <th className="px-6 py-3">Description</th>
                  <th className="px-6 py-3">Type</th>
                  <th className="px-6 py-3 text-right">Amount</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-50">
                {isLoading ? (
                  <tr><td colSpan={4} className="px-6 py-10 text-center text-slate-400"><Loader2 className="h-6 w-6 animate-spin mx-auto mb-2 text-amber-500" />Syncing ledger…</td></tr>
                ) : transactions.length === 0 ? (
                  <tr><td colSpan={4} className="px-6 py-14 text-center"><Receipt className="h-10 w-10 text-slate-200 mx-auto mb-2" /><p className="text-slate-400 text-sm">No transactions yet.</p></td></tr>
                ) : transactions.map((tx) => (
                  <tr key={tx.id || tx.reference || Date.now()} onClick={() => setSelectedTx(tx)} className="hover:bg-slate-50 cursor-pointer transition-colors">
                    <td className="px-6 py-4 text-slate-500 text-xs whitespace-nowrap">{new Date(tx.created_at).toLocaleDateString("en-IN")}</td>
                    <td className="px-6 py-4 text-slate-800 font-semibold">{tx.description || tx.reference}</td>
                    <td className="px-6 py-4">
                      <span className={`px-2.5 py-1 text-xs font-bold rounded-lg ${
                        tx.transaction_type?.includes("credit") || tx.transaction_type?.includes("commission") || tx.transaction_type?.includes("in")
                          ? "bg-emerald-100 text-emerald-800" : "bg-amber-100 text-amber-800"
                      }`}>
                        {tx.transaction_type?.replace(/_/g, " ").toUpperCase()}
                      </span>
                    </td>
                    <td className={`px-6 py-4 text-right font-bold whitespace-nowrap ${tx.amount > 0 ? "text-emerald-600" : "text-slate-700"}`}>
                      {tx.amount > 0 ? "+" : ""}₹{parseFloat(Math.abs(tx.amount)).toFixed(2)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Transaction detail modal */}
        {selectedTx && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-in fade-in">
            <div className="bg-white rounded-2xl shadow-2xl w-full max-w-sm overflow-hidden animate-in zoom-in-95">
              <div className="px-5 py-4 border-b border-slate-100 flex justify-between items-center bg-slate-50">
                <h3 className="font-bold text-slate-900">Transaction Detail</h3>
                <button onClick={() => setSelectedTx(null)} className="p-1.5 text-slate-400 hover:text-slate-900 bg-white rounded-full shadow-sm">
                  <X className="h-4 w-4" />
                </button>
              </div>
              <div className="p-5 space-y-3">
                {[
                  { label: "Date", value: new Date(selectedTx.created_at).toLocaleString("en-IN") },
                  { label: "Description", value: selectedTx.description || selectedTx.reference },
                  { label: "Type", value: selectedTx.transaction_type?.replace(/_/g, " ").toUpperCase() },
                  { label: "Amount", value: `${selectedTx.amount > 0 ? "+" : ""}₹${parseFloat(Math.abs(selectedTx.amount)).toFixed(2)}` },
                ].map((r) => (
                  <div key={r.label} className="flex justify-between items-center py-2 border-b border-slate-50">
                    <span className="text-xs text-slate-400 font-semibold uppercase tracking-wider">{r.label}</span>
                    <span className="text-sm font-bold text-slate-800">{r.value}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Withdraw modal */}
        <ModalWrapper open={isWithdrawOpen} onClose={() => setIsWithdrawOpen(false)}>
          <div className="px-5 py-4 border-b border-slate-100 flex justify-between items-center bg-slate-50 shrink-0">
            <h3 className="font-bold text-slate-900">Request Payout</h3>
            <button onClick={() => setIsWithdrawOpen(false)} className="p-1.5 text-slate-400 hover:text-slate-900 bg-white rounded-full shadow-sm"><X className="h-4 w-4" /></button>
          </div>
          <div className="p-5 overflow-y-auto space-y-5">
            <StatusAlert status={withdrawStatus} />
            <div className="bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 flex justify-between items-center">
              <span className="text-xs font-semibold text-slate-500">Available</span>
              <span className="font-black text-amber-600">₹{parseFloat(balance).toFixed(2)}</span>
            </div>
            <form onSubmit={handleWithdraw} className="space-y-5">
              <div>
                <label className="block text-sm font-semibold text-slate-700 mb-1.5">Withdrawal Amount (₹)</label>
                <input type="number" min="1" step="0.01" value={withdrawAmount} onChange={(e) => setWithdrawAmount(e.target.value)} placeholder="e.g. 1500" className="w-full px-4 py-3 border border-slate-300 rounded-xl text-lg font-bold focus:ring-2 focus:ring-amber-500 outline-none" />
              </div>
              <div>
                <label className="block text-sm font-semibold text-slate-700 mb-2">Payout Method</label>
                <div className="flex gap-2">
                  {["upi", "bank"].map((m) => (
                    <button key={m} type="button" onClick={() => setPayoutMethod(m)} className={`flex-1 py-2.5 rounded-xl border-2 text-sm font-bold transition-all ${payoutMethod === m ? "bg-amber-50 border-amber-500 text-amber-700" : "bg-white border-slate-200 text-slate-500"}`}>
                      {m === "upi" ? "UPI" : "Bank Transfer"}
                    </button>
                  ))}
                </div>
              </div>
              {payoutMethod === "upi" ? (
                <div className="space-y-3 bg-slate-50 p-4 rounded-xl border border-slate-100">
                  <div><label className="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-1">UPI ID</label><input type="text" placeholder="example@upi" value={payoutDetails.upiId} onChange={(e) => setPayoutDetails({ ...payoutDetails, upiId: e.target.value })} className="w-full px-3 py-2.5 border border-slate-200 rounded-xl text-sm focus:ring-2 focus:ring-amber-500 outline-none" /></div>
                  <div><label className="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-1">UPI Mobile</label><input type="text" placeholder="9876543210" value={payoutDetails.upiMobile} onChange={(e) => setPayoutDetails({ ...payoutDetails, upiMobile: e.target.value })} className="w-full px-3 py-2.5 border border-slate-200 rounded-xl text-sm focus:ring-2 focus:ring-amber-500 outline-none" /></div>
                </div>
              ) : (
                <div className="space-y-3 bg-slate-50 p-4 rounded-xl border border-slate-100">
                  <div><label className="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-1">Account Number</label><input type="text" placeholder="Account Number" value={payoutDetails.bankAccount} onChange={(e) => setPayoutDetails({ ...payoutDetails, bankAccount: e.target.value })} className="w-full px-3 py-2.5 border border-slate-200 rounded-xl text-sm focus:ring-2 focus:ring-amber-500 outline-none" /></div>
                  <div><label className="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-1">IFSC Code</label><input type="text" placeholder="IFSC Code" value={payoutDetails.bankIfsc} onChange={(e) => setPayoutDetails({ ...payoutDetails, bankIfsc: e.target.value })} className="w-full px-3 py-2.5 border border-slate-200 rounded-xl text-sm focus:ring-2 focus:ring-amber-500 outline-none" /></div>
                </div>
              )}
              <button type="submit" disabled={isWithdrawing || !withdrawAmount} className="w-full py-3.5 bg-amber-600 hover:bg-amber-700 text-white font-bold rounded-xl transition-all disabled:opacity-50 flex items-center justify-center gap-2">
                {isWithdrawing ? <Loader2 className="h-5 w-5 animate-spin" /> : "Submit Request"}
              </button>
            </form>
          </div>
        </ModalWrapper>

        {/* Transfer modal */}
        <ModalWrapper open={isTransferOpen} onClose={() => setIsTransferOpen(false)}>
          <div className="px-5 py-4 border-b border-slate-100 flex justify-between items-center bg-slate-50 shrink-0">
            <h3 className="font-bold text-slate-900">Transfer Funds</h3>
            <button onClick={() => setIsTransferOpen(false)} className="p-1.5 text-slate-400 hover:text-slate-900 bg-white rounded-full shadow-sm"><X className="h-4 w-4" /></button>
          </div>
          <div className="p-5 space-y-5">
            <StatusAlert status={transferStatus} />
            <div className="bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 flex justify-between items-center">
              <span className="text-xs font-semibold text-slate-500">Available</span>
              <span className="font-black text-slate-900">₹{parseFloat(balance).toFixed(2)}</span>
            </div>
            <form onSubmit={handleTransfer} className="space-y-4">
              <div><label className="block text-sm font-semibold text-slate-700 mb-1.5">Receiver ID or Email</label><input type="text" value={transferReceiver} onChange={(e) => setTransferReceiver(e.target.value)} placeholder="e.g. 45 or john@email.com" className="w-full px-4 py-3 border border-slate-300 rounded-xl text-sm font-medium focus:ring-2 focus:ring-slate-900 outline-none" /></div>
              <div><label className="block text-sm font-semibold text-slate-700 mb-1.5">Amount (₹)</label><input type="number" min="1" step="0.01" value={transferAmount} onChange={(e) => setTransferAmount(e.target.value)} placeholder="e.g. 500" className="w-full px-4 py-3 border border-slate-300 rounded-xl text-lg font-bold focus:ring-2 focus:ring-slate-900 outline-none" /></div>
              <button type="submit" disabled={isTransferring || !transferAmount || !transferReceiver} className="w-full py-3.5 bg-[#0f2a1f] hover:bg-[#1a3a2a] text-white font-bold rounded-xl transition-all disabled:opacity-50 flex items-center justify-center gap-2">
                {isTransferring ? <Loader2 className="h-5 w-5 animate-spin" /> : "Send Funds Instantly"}
              </button>
            </form>
          </div>
        </ModalWrapper>
      </div>
    );
  };

  // ---------------------------------------------------------
  // 6. NETWORK TAB (ENTERPRISE ORG CHART & DIRECTORY)
  // ---------------------------------------------------------
  const NetworkTab = () => {
    const [networkStats, setNetworkStats] = useState({ total: 0, direct: [] });
    const [treeData, setTreeData] = useState(null);
    const [uplineData, setUplineData] = useState([]);
    const [flatTeam, setFlatTeam] = useState([]);
    const [isLoading, setIsLoading] = useState(true);
    const [viewMode, setViewMode] = useState("tree"); 

    useEffect(() => {
      const loadNetwork = async () => {
        setIsLoading(true);
        try {
          // Fetch tree, stats, and upline simultaneously
          const [networkRes, uplineRes] = await Promise.all([
            fetchNetworkData(),
            fetchUplineData()
          ]);

          if (networkRes.success) {
            setNetworkStats({ total: networkRes.totalCount, direct: networkRes.directTeam });
            setTreeData(networkRes.tree);

            // Flatten tree for the directory table
            const flattenTree = (node, depth = 1) => {
              let list = [];
              if (node && node.user_id && depth > 1) { // Skip root node for downline list
                 list.push({ 
                   id: node.user_id, 
                   name: node.full_name || `User #${node.user_id}`, 
                   email: node.email || 'N/A',
                   phone: node.phone || 'N/A',
                   level: depth - 1, 
                   status: node.is_active ? 'Active' : 'Inactive', 
                   joinDate: node.created_at || new Date().toISOString() 
                 });
              }
              if (node && node.children) {
                 node.children.forEach(child => { list = list.concat(flattenTree(child, depth + 1)); });
              }
              return list;
            };
            
            if (networkRes.tree && Object.keys(networkRes.tree).length > 0) {
              setFlatTeam(flattenTree(networkRes.tree));
            }
          }

          if (uplineRes.success && uplineRes.data) {
            setUplineData(uplineRes.data);
          }
        } catch (error) {
          console.error("Failed to compile network view", error);
        }
        setIsLoading(false);
      };
      loadNetwork();
    }, []);

    // Custom Recursive Component for the Top-Down Org Chart
    const OrgChartNode = ({ node, isRoot = false }) => {
      const [expanded, setExpanded] = useState(true);
      const hasChildren = node.children && node.children.length > 0;

      return (
        <div className="flex flex-col items-center">
          {/* Card UI */}
          <div 
            onClick={() => hasChildren && setExpanded(!expanded)}
            className={`relative z-10 w-72 bg-white rounded-2xl shadow-md border-2 transition-all duration-300 ${isRoot ? 'border-indigo-500 shadow-indigo-100' : node.is_active ? 'border-emerald-500 hover:shadow-emerald-100 cursor-pointer' : 'border-slate-200 cursor-pointer'}`}
          >
            <div className={`p-4 border-b flex justify-between items-center ${isRoot ? 'bg-indigo-50' : node.is_active ? 'bg-emerald-50' : 'bg-slate-50'} rounded-t-2xl`}>
              <div className="flex items-center">
                <div className={`h-10 w-10 rounded-full flex items-center justify-center font-black text-white shadow-inner ${isRoot ? 'bg-indigo-500' : node.is_active ? 'bg-emerald-500' : 'bg-slate-400'}`}>
                  {node.full_name ? node.full_name.charAt(0).toUpperCase() : 'U'}
                </div>
                <div className="ml-3">
                  <h4 className="font-black text-slate-900 leading-tight truncate w-32">{node.full_name || `User #${node.user_id}`}</h4>
                  <p className="text-xs font-bold text-slate-500 mt-0.5">ID: {node.user_id}</p>
                </div>
              </div>
              <span className={`text-[10px] font-black uppercase tracking-wider px-2 py-1 rounded-md ${node.is_active ? 'bg-emerald-200 text-emerald-800' : 'bg-slate-200 text-slate-600'}`}>
                {node.is_active ? 'Active' : 'Inactive'}
              </span>
            </div>
            <div className="p-4 space-y-2 bg-white rounded-b-2xl">
              <div className="flex justify-between items-center text-xs">
                <span className="font-semibold text-slate-500">Rank</span>
                <span className="font-black text-indigo-600">{isRoot ? user.rank || 'Distributor' : 'Distributor'}</span>
              </div>
              <div className="flex justify-between items-center text-xs">
                <span className="font-semibold text-slate-500">Phone</span>
                <span className="font-bold text-slate-800">{node.phone || 'N/A'}</span>
              </div>
              <div className="flex justify-between items-center text-xs">
                <span className="font-semibold text-slate-500">Email</span>
                <span className="font-bold text-slate-800 truncate w-32 text-right">{node.email || 'N/A'}</span>
              </div>
            </div>
            {/* Expand Indicator */}
            {hasChildren && (
              <div className="absolute -bottom-3 left-1/2 transform -translate-x-1/2 bg-white border-2 border-slate-200 rounded-full h-6 w-6 flex items-center justify-center text-slate-500 shadow-sm font-bold text-lg leading-none z-20">
                {expanded ? '-' : '+'}
              </div>
            )}
          </div>

          {/* Children & Connecting Lines */}
          {expanded && hasChildren && (
            <div className="flex flex-col items-center">
              {/* Vertical line dropping down from parent */}
              <div className="w-0.5 h-6 bg-slate-300"></div>
              {/* Container for children */}
              <div className="flex gap-6 relative pt-4">
                {/* Horizontal line bridging the children */}
                {node.children.length > 1 && (
                  <div className="absolute top-0 left-0 w-full h-0.5 bg-slate-300" style={{ width: `calc(100% - ${100 / node.children.length}%)`, left: `calc(${50 / node.children.length}%)` }}></div>
                )}
                {/* Map over children, mapping short vertical drop lines to their cards */}
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
          <div className="w-full bg-slate-100/50 rounded-[2rem] border-2 border-slate-200 overflow-x-auto overflow-y-auto mt-8 p-12 min-h-[600px] custom-scrollbar shadow-inner">
            {treeData ? (
              <div className="min-w-max flex justify-center pb-20">
                <OrgChartNode node={treeData} isRoot={true} />
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center h-full text-slate-500">
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
                  <tr><th className="px-8 py-5">Member Details</th><th className="px-8 py-5 text-center">Generation Level</th><th className="px-8 py-5">Contact</th><th className="px-8 py-5 text-right">Status</th></tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {flatTeam.length === 0 ? <tr><td colSpan="4" className="px-8 py-16 text-center text-slate-500"><Users className="h-12 w-12 text-slate-200 mx-auto mb-3"/>Your network is currently empty.</td></tr>
                  : flatTeam.map((member, idx) => (
                    <tr key={idx} className="hover:bg-slate-50 transition-colors">
                      <td className="px-8 py-6">
                        <div className="flex items-center">
                          <div className="h-12 w-12 rounded-xl bg-gradient-to-br from-emerald-100 to-teal-100 flex items-center justify-center text-emerald-700 text-xl font-black mr-4 shadow-inner border border-emerald-200">
                            {member.name.charAt(0).toUpperCase()}
                          </div>
                          <div>
                            <span className="text-slate-900 font-black text-lg block leading-tight">{member.name}</span>
                            <span className="text-xs font-bold text-slate-400 mt-1">ID: #{member.id} • Joined {new Date(member.joinDate).toLocaleDateString('en-IN')}</span>
                          </div>
                        </div>
                      </td>
                      <td className="px-8 py-6 text-center"><span className="px-5 py-2 bg-slate-100 border border-slate-200 text-slate-700 rounded-xl font-black text-sm shadow-sm">Level {member.level}</span></td>
                      <td className="px-8 py-6">
                        <p className="font-bold text-slate-800 text-sm mb-1">{member.phone}</p>
                        <p className="text-xs font-semibold text-slate-500">{member.email}</p>
                      </td>
                      <td className="px-8 py-6 text-right"><span className={`px-4 py-2 text-xs font-black rounded-xl uppercase tracking-wider border shadow-sm ${member.status === 'Active' ? 'bg-emerald-50 text-emerald-700 border-emerald-200' : 'bg-slate-50 text-slate-500 border-slate-200'}`}>{member.status}</span></td>
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

  // ─────────────────────────────────────────────────────────────────
  // TAB: PRODUCT CATALOG (unchanged except color inheritance)
  // ─────────────────────────────────────────────────────────────────
  const ProductCatalogTab = () => {
    const [packages, setPackages] = useState([]);
    const [isLoading, setIsLoading] = useState(true);
    const [buyStatus, setBuyStatus] = useState({ type: "", msg: "" });
    const [isPurchasing, setIsPurchasing] = useState(null);
    const [showSuccessModal, setShowSuccessModal] = useState(false);
    const [purchasedPlan, setPurchasedPlan] = useState(null);
    const [confirmPkg, setConfirmPkg] = useState(null);

    useEffect(() => {
      const loadData = async () => {
        setIsLoading(true);
        try {
          const pkgRes = await fetchPackages();
          if (pkgRes.success) setPackages(pkgRes.data);
        } catch (e) { /* API pending */ }
        setIsLoading(false);
      };
      loadData();
    }, []);

    const handleBuy = async (pkg) => {
      setConfirmPkg(null);
      setIsPurchasing(pkg.id);
      setBuyStatus({ type: "", msg: "" });
      try {
        const res = await purchasePlan(pkg.id);
        if (res.success) { setPurchasedPlan(pkg); setShowSuccessModal(true); }
        else { setBuyStatus({ type: "error", msg: res.message }); }
      } catch (e) { setBuyStatus({ type: "error", msg: "Purchase failed. Please try again." }); }
      setIsPurchasing(null);
    };

    return (
      <div className="max-w-6xl mx-auto space-y-8 pb-10 animate-in fade-in slide-in-from-bottom-4 duration-500">
        {showSuccessModal && purchasedPlan && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/70 backdrop-blur-sm animate-in fade-in">
            <div className="bg-white rounded-2xl shadow-2xl w-full max-w-sm overflow-hidden animate-in zoom-in-95 text-center p-8">
              <div className="w-20 h-20 bg-amber-100 rounded-full flex items-center justify-center mx-auto mb-5 border-4 border-white shadow">
                <CheckCircle2 className="h-10 w-10 text-amber-600" />
              </div>
              <h2 className="text-2xl font-black text-slate-900 mb-1">Payment Successful!</h2>
              <p className="text-slate-500 text-sm mb-6">You activated <strong>{purchasedPlan.name}</strong>.</p>
              <div className="bg-slate-50 p-4 rounded-xl border border-slate-100 mb-6 text-left space-y-2">
                <div className="flex justify-between items-center">
                  <span className="text-xs text-slate-400 font-semibold">Amount Paid</span>
                  <span className="font-bold text-slate-900">₹{parseFloat(purchasedPlan.price).toLocaleString("en-IN")}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-xs text-slate-400 font-semibold">Status</span>
                  <span className="text-xs font-bold bg-amber-100 text-amber-700 px-2.5 py-0.5 rounded-full">Activated</span>
                </div>
              </div>
              <button onClick={() => { setShowSuccessModal(false); switchTab("My Orders & Invoices"); }} className="w-full py-3 bg-[#0f2a1f] hover:bg-[#1a3a2a] text-white font-bold rounded-xl text-sm transition-all">
                View Tax Invoice
              </button>
            </div>
          </div>
        )}

        {confirmPkg && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-in fade-in">
            <div className="bg-white rounded-2xl shadow-2xl w-full max-w-sm p-6 animate-in zoom-in-95">
              <h3 className="font-bold text-slate-900 mb-2">Confirm Purchase</h3>
              <p className="text-sm text-slate-500 mb-6">You are about to activate <strong>{confirmPkg.name}</strong> for <strong>₹{parseFloat(confirmPkg.price).toLocaleString("en-IN")}</strong>. This is a one-time, non-refundable activation fee.</p>
              <div className="flex gap-3">
                <button onClick={() => setConfirmPkg(null)} className="flex-1 py-2.5 border border-slate-200 text-slate-600 font-semibold rounded-xl text-sm hover:bg-slate-50 transition-all">Cancel</button>
                <button onClick={() => handleBuy(confirmPkg)} className="flex-1 py-2.5 bg-amber-600 hover:bg-amber-700 text-white font-bold rounded-xl text-sm transition-all">Yes, Confirm</button>
              </div>
            </div>
          </div>
        )}

        <div className="flex flex-col sm:flex-row sm:justify-between sm:items-end gap-4">
          <div>
            <h2 className="text-2xl font-black text-slate-900">Product Catalog</h2>
            <p className="text-slate-500 text-sm mt-1">Choose an activation plan to unlock your earning potential.</p>
          </div>
          <button onClick={() => window.print()} className="print:hidden flex items-center gap-2 px-5 py-2.5 bg-white border border-slate-200 text-slate-600 hover:bg-slate-50 rounded-xl text-sm font-semibold transition-all">
            <Download className="h-4 w-4" /> Download Brochure
          </button>
        </div>

        {buyStatus.msg && (
          <div className={`p-4 rounded-xl border flex items-center gap-3 ${buyStatus.type === "error" ? "bg-red-50 border-red-200 text-red-700" : "bg-emerald-50 border-emerald-200 text-emerald-700"}`}>
            <AlertCircle className="h-4 w-4 shrink-0" /><p className="text-sm font-semibold">{buyStatus.msg}</p>
          </div>
        )}

        {isLoading ? (
          <div className="flex justify-center py-20"><Loader2 className="h-8 w-8 text-amber-500 animate-spin" /></div>
        ) : packages.length === 0 ? (
          <div className="text-center p-10 bg-white rounded-2xl border border-slate-100">
            <ShoppingBag className="h-10 w-10 text-slate-300 mx-auto mb-3" />
            <h3 className="font-bold text-slate-700">No plans available yet.</h3>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {packages.map((pkg) => (
              <div key={pkg.id} className={`bg-white rounded-2xl shadow-sm hover:shadow-xl hover:-translate-y-1 transition-all duration-200 border flex flex-col overflow-hidden group relative ${pkg.is_popular ? "border-amber-500" : "border-slate-100"}`}>
                {pkg.is_popular && (
                  <div className="absolute top-0 inset-x-0 bg-amber-500 text-white text-[10px] font-black uppercase tracking-widest text-center py-1.5 z-10">
                    Most Popular
                  </div>
                )}
                <div className={`h-48 bg-slate-100 border-b border-slate-100 overflow-hidden ${pkg.is_popular ? "mt-6" : ""}`}>
                  {pkg.image_url
                    ? <img src={pkg.image_url} alt={pkg.name} className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500" />
                    : <div className="flex items-center justify-center h-full"><ImageIcon className="h-14 w-14 text-slate-200" /></div>
                  }
                </div>
                <div className="p-6 pb-3">
                  <h3 className="text-xl font-black text-slate-900">{pkg.name}</h3>
                  <div className="flex items-baseline gap-1 mt-2">
                    <span className="text-sm font-bold text-amber-400">₹</span>
                    <span className="text-4xl font-black text-amber-600">{parseFloat(pkg.price).toFixed(0)}</span>
                  </div>
                  <p className="text-slate-400 text-xs font-semibold mt-1 uppercase tracking-wider">One-time activation</p>
                </div>
                <div className="p-6 pt-0 flex-1 flex flex-col">
                  <ul className="space-y-3 flex-1 mt-3">
                    <li className="flex items-center gap-2.5 text-sm font-medium text-slate-700">
                      <Zap className="h-4 w-4 text-amber-500 shrink-0" />
                      {pkg.lucky_draw_coupons || 0} Lucky Draw Coupons
                    </li>
                    <li className="flex items-center gap-2.5 text-sm font-medium text-slate-700">
                      <CheckCircle2 className="h-4 w-4 text-emerald-500 shrink-0" />
                      Multi-Level Commissions Access
                    </li>
                    {pkg.description && (
                      <li className="flex items-start gap-2.5 text-sm font-medium text-slate-600">
                        <Star className="h-4 w-4 text-indigo-400 shrink-0 mt-0.5" />{pkg.description}
                      </li>
                    )}
                  </ul>
                  <button
                    onClick={() => setConfirmPkg(pkg)}
                    disabled={!!isPurchasing}
                    className={`print:hidden mt-6 w-full py-3 rounded-xl font-bold text-sm shadow-sm transition-all flex items-center justify-center gap-2 hover:-translate-y-0.5
                      ${pkg.is_popular
                        ? "bg-amber-600 hover:bg-amber-700 text-white"
                        : "bg-[#0f2a1f] hover:bg-[#1a3a2a] text-white"
                      } disabled:opacity-50`}
                  >
                    {isPurchasing === pkg.id ? <Loader2 className="h-4 w-4 animate-spin" /> : "Activate Plan"}
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  };

  // ─────────────────────────────────────────────────────────────────
  // TAB RENDERER (unchanged)
  // ─────────────────────────────────────────────────────────────────
  const renderTab = () => {
    switch (activeTab) {
      case "Overview":          return <OverviewTab />;
      case "Company Info":      return <CompanyInfoTab />;
      case "My Profile":        return <ProfileTab />;
      case "KYC Verification":  return <KycTab />;
      case "My Network Tree":   return <NetworkTab />;
      case "Wallet & Payouts":  return <WalletTab />;
      case "Product Catalog":   return <ProductCatalogTab />;
      case "My Orders & Invoices": return (
        <div className="flex flex-col items-center justify-center py-20 text-slate-400">
          <Receipt className="h-14 w-14 text-slate-200 mb-3" />
          <p className="font-semibold">Orders & Invoices</p>
          <p className="text-sm mt-1">Backend integration pending.</p>
        </div>
      );
      case "Help & Support": return (
        <div className="flex flex-col items-center justify-center py-20 text-slate-400">
          <LifeBuoy className="h-14 w-14 text-slate-200 mb-3" />
          <p className="font-semibold">Help & Support</p>
          <p className="text-sm mt-1">Backend integration pending.</p>
        </div>
      );
      default: return null;
    }
  };

  // ─────────────────────────────────────────────────────────────────
  // LAYOUT – PREMIUM DARK GREEN SIDEBAR + CREAM BACKGROUND
  // ─────────────────────────────────────────────────────────────────
  return (
    <div className="min-h-screen bg-[#faf8f5] flex">
      {/* Mobile overlay */}
      {sidebarOpen && (
        <div className="fixed inset-0 z-20 bg-slate-900/50 lg:hidden" onClick={() => setSidebarOpen(false)} />
      )}

      {/* Sidebar – deep forest green */}
      <aside className={`
        fixed top-0 left-0 h-full z-30 w-64 bg-[#0f2a1f] border-r border-[#1a3a2a] flex flex-col
        transition-transform duration-300 ease-in-out
        ${sidebarOpen ? "translate-x-0" : "-translate-x-full"}
        lg:translate-x-0 lg:static lg:flex
      `}>
        {/* Logo */}
        <div className="px-5 py-5 border-b border-[#1a3a2a]">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-amber-500 rounded-lg flex items-center justify-center">
              <Globe className="h-4 w-4 text-white" />
            </div>
            <span className="font-black text-[#e8dcc8] tracking-tight">RK Trendz</span>
          </div>
        </div>

        {/* User info strip */}
        <div className="px-4 py-3 border-b border-[#1a3a2a] bg-[#0f2a1f]/80">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-amber-300 to-amber-500 flex items-center justify-center text-[#0f2a1f] font-bold text-sm shrink-0">
              {user.full_name.charAt(0).toUpperCase()}
            </div>
            <div className="min-w-0">
              <p className="text-sm font-bold text-[#e8dcc8] truncate">{user.full_name}</p>
              <p className="text-[10px] text-amber-200/60 truncate">{user.email}</p>
            </div>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 p-3 space-y-0.5 overflow-y-auto">
          {menuItems.map((item) => {
            const isActive = activeTab === item.name;
            return (
              <button
                key={item.name}
                onClick={() => switchTab(item.name)}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-semibold transition-all text-left
                  ${isActive
                    ? "bg-amber-500/20 text-amber-300 border border-amber-500/30"
                    : "text-[#c4b89a] hover:bg-[#1a3a2a] hover:text-[#e8dcc8]"
                  }`}
              >
                <item.icon className={`h-4 w-4 shrink-0 ${isActive ? "text-amber-400" : "text-[#c4b89a]"}`} />
                {item.name}
              </button>
            );
          })}
        </nav>

        {/* Logout */}
        <div className="p-3 border-t border-[#1a3a2a]">
          <button
            onClick={() => { logout(); router.push("/login"); }}
            className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-semibold text-[#c4b89a] hover:bg-red-500/20 hover:text-red-400 transition-all"
          >
            <LogOut className="h-4 w-4 shrink-0" /> Log Out
          </button>
        </div>
      </aside>

      {/* Main content */}
      <div className="flex-1 flex flex-col min-w-0 lg:pl-0">
        {/* Top bar */}
        <header className="sticky top-0 z-10 bg-white/90 backdrop-blur-md border-b border-amber-100/50 px-4 lg:px-8 py-3.5 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button onClick={() => setSidebarOpen(true)} className="lg:hidden p-2 text-slate-500 hover:text-slate-900 hover:bg-slate-100 rounded-lg transition-all">
              <Menu className="h-5 w-5" />
            </button>
            <div>
              <h1 className="text-base font-bold text-slate-900">{activeTab}</h1>
              <p className="text-[10px] text-slate-400 hidden sm:block">RK Trendz Member Portal</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className="hidden sm:flex items-center gap-1.5 px-3 py-1.5 bg-amber-50 text-amber-700 text-xs font-bold rounded-full border border-amber-100">
              <span className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse" />
              Active
            </span>
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 p-4 lg:p-8 overflow-y-auto">
          {renderTab()}
        </main>
      </div>
    </div>
  );
}
