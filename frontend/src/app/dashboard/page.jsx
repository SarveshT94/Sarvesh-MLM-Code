"use client";

import { useEffect, useState, useRef } from "react";
import useAuthStore from "@/store/authStore";
import { useRouter } from "next/navigation";
import { requestProfileUpdate, verifyProfileOtp } from "@/services/profile";
import { 
  LayoutDashboard, UserCircle, Users, ShoppingBag, 
  Wallet, LogOut, Share2, Copy, CheckCircle2, TrendingUp, Camera, ShieldCheck, AlertCircle, Loader2
} from "lucide-react";

export default function DashboardPage() {
  const { user, isAuthenticated, isChecking, logout, setAuth } = useAuthStore();
  const router = useRouter();
  
  const [activeTab, setActiveTab] = useState("Overview"); 
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!isChecking && !isAuthenticated) {
      router.push("/login");
    }
  }, [isAuthenticated, isChecking, router]);

  if (isChecking || !isAuthenticated || !user) return null;

  // 🔥 FIXED: Safe Fallback for Referral Code
  const refCode = user?.referral_code || "PENDING";
  const shareUrl = `http://localhost:3000/register?ref=${refCode}`;

  const handleShare = async () => {
    const shareData = {
      title: 'Join my RK Trendz Network!',
      text: `Sign up using my referral code: ${refCode} and join my team!`,
      url: shareUrl,
    };
    try {
      if (navigator.share) {
        await navigator.share(shareData);
      } else {
        handleCopy();
      }
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
    { name: "My Profile", icon: UserCircle },
    { name: "My Network Tree", icon: Users },
    { name: "Wallet & Payouts", icon: Wallet },
    { name: "Product Catalog", icon: ShoppingBag },
  ];

  const OverviewTab = () => (
    <>
      <div className="mb-8">
        <h2 className="text-2xl font-bold text-slate-900 sm:text-3xl">
          Welcome back, {user.full_name.split(' ')[0]}! 👋
        </h2>
        <p className="mt-1 text-sm text-slate-500">
          Here is your network and financial overview for today.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-5 sm:grid-cols-3 mb-8">
        <div className="bg-white overflow-hidden shadow-sm border border-slate-200 rounded-2xl relative">
          <div className="p-5">
            <div className="flex items-center">
              <div className="flex-shrink-0 bg-emerald-100 rounded-xl p-3">
                <Wallet className="h-6 w-6 text-emerald-600" />
              </div>
              <div className="ml-5 w-0 flex-1">
                <dl>
                  <dt className="text-sm font-medium text-slate-500 truncate">Total Wallet Balance</dt>
                  <dd className="text-2xl font-bold text-slate-900 mt-1">₹0.00</dd>
                </dl>
              </div>
            </div>
          </div>
          <div className="bg-slate-50 px-5 py-3 border-t border-slate-100">
            <button 
              onClick={() => setActiveTab("Wallet & Payouts")}
              className="text-sm font-semibold text-emerald-600 hover:text-emerald-700 flex items-center"
            >
              Request Withdrawal <TrendingUp className="ml-1 h-4 w-4" />
            </button>
          </div>
        </div>

        <div className="bg-white overflow-hidden shadow-sm border border-slate-200 rounded-2xl">
          <div className="p-5">
            <div className="flex items-center">
              <div className="flex-shrink-0 bg-blue-100 rounded-xl p-3">
                <Users className="h-6 w-6 text-blue-600" />
              </div>
              <div className="ml-5 w-0 flex-1">
                <dl>
                  <dt className="text-sm font-medium text-slate-500 truncate">Active Downline</dt>
                  <dd className="text-2xl font-bold text-slate-900 mt-1">0 Members</dd>
                </dl>
              </div>
            </div>
          </div>
          <div className="bg-slate-50 px-5 py-3 border-t border-slate-100">
            <button 
              onClick={() => setActiveTab("My Network Tree")} 
              className="text-sm font-semibold text-blue-600 hover:text-blue-700"
            >
              View Network Tree
            </button>
          </div>
        </div>

        <div className="bg-white overflow-hidden shadow-sm border border-slate-200 rounded-2xl">
          <div className="p-5">
            <div className="flex items-center">
              <div className="flex-shrink-0 bg-purple-100 rounded-xl p-3">
                <CheckCircle2 className="h-6 w-6 text-purple-600" />
              </div>
              <div className="ml-5 w-0 flex-1">
                <dl>
                  <dt className="text-sm font-medium text-slate-500 truncate">Current Plan</dt>
                  <dd className="text-xl font-bold text-slate-900 mt-1">Free Tier</dd>
                </dl>
              </div>
            </div>
          </div>
          <div className="bg-slate-50 px-5 py-3 border-t border-slate-100">
            <button 
              onClick={() => setActiveTab("Product Catalog")} 
              className="text-sm font-semibold text-purple-600 hover:text-purple-700"
            >
              Upgrade Plan
            </button>
          </div>
        </div>
      </div>

      <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 mb-8 lg:w-2/3">
        <h3 className="text-lg font-bold text-slate-900 mb-4">Grow Your Network</h3>
        <p className="text-sm text-slate-500 mb-5">
          Share your unique referral code with friends. You will earn commissions when they join and activate a plan.
        </p>
        
        <div className="flex flex-col sm:flex-row gap-4">
          <div className="flex-1 bg-slate-50 border border-slate-200 rounded-lg p-4 flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">Your Referral Code</p>
              {/* 🔥 FIXED: UI uses refCode fallback */}
              <p className="text-xl font-black text-emerald-600 tracking-widest">{refCode}</p>
            </div>
            <button 
              onClick={handleCopy}
              disabled={refCode === "PENDING"}
              className="p-2 bg-white border border-slate-200 rounded-md hover:bg-slate-50 transition-colors shadow-sm text-slate-600 disabled:opacity-50"
              title="Copy to clipboard"
            >
              {copied ? <CheckCircle2 className="h-5 w-5 text-emerald-500" /> : <Copy className="h-5 w-5" />}
            </button>
          </div>

          <button 
            onClick={handleShare}
            disabled={refCode === "PENDING"}
            className="flex items-center justify-center px-6 py-4 bg-emerald-600 hover:bg-emerald-700 text-white font-bold rounded-lg shadow-md transition-all sm:w-auto disabled:opacity-50"
          >
            <Share2 className="mr-2 h-5 w-5" />
            Share Link
          </button>
        </div>
      </div>
    </>
  );

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
      setStatus({ type: "", msg: "" });
      setIsLoading(true);
      
      const newIdentifier = type === 'email' ? form.email : form.phone;
      const res = await requestProfileUpdate(type, newIdentifier);
      
      if (res.success) {
        setStatus({ type: "success", msg: res.data.message });
        setActiveVerification(type);
      } else {
        setStatus({ type: "error", msg: res.message });
      }
      setIsLoading(false);
    };

    const handleVerifyOtp = async () => {
      if (otpCode.length !== 6) {
        setStatus({ type: "error", msg: "Please enter a valid 6-digit OTP." });
        return;
      }
      setIsLoading(true);
      setStatus({ type: "", msg: "" });

      const res = await verifyProfileOtp(otpCode);
      
      if (res.success) {
        setStatus({ type: "success", msg: res.data.message });
        setAuth({ ...user, [activeVerification]: form[activeVerification] });
        setActiveVerification(null);
        setOtpCode("");
      } else {
        setStatus({ type: "error", msg: res.message });
      }
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
                  {photoPreview ? (
                    <img src={photoPreview} alt="Profile" className="h-full w-full object-cover" />
                  ) : (
                    <div className="h-full w-full flex items-center justify-center bg-emerald-100 text-emerald-600 text-4xl font-bold">
                      {user.full_name.charAt(0).toUpperCase()}
                    </div>
                  )}
                </div>
                <div className="absolute inset-0 bg-slate-900/40 rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
                  <Camera className="h-8 w-8 text-white" />
                </div>
                <input type="file" ref={fileInputRef} onChange={handlePhotoChange} accept="image/*" className="hidden" />
              </div>
              <h3 className="text-xl font-bold text-slate-900">{user.full_name}</h3>
              <p className="text-sm font-medium text-emerald-600 bg-emerald-50 inline-block px-3 py-1 rounded-full mt-2 border border-emerald-100">
                Rank: Affiliate
              </p>
            </div>
          </div>

          <div className="md:col-span-2 space-y-6">
            <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
              <div className="px-6 py-5 border-b border-slate-100 bg-slate-50/50">
                <h3 className="text-lg font-bold text-slate-900 flex items-center">
                  <ShieldCheck className="h-5 w-5 mr-2 text-slate-400" /> Contact & Security
                </h3>
              </div>
              
              <div className="p-6 space-y-6">
                <div className="space-y-3">
                  <label className="block text-sm font-semibold text-slate-700">Email Address</label>
                  <div className="flex gap-3">
                    <input
                      type="email"
                      value={form.email}
                      disabled={activeVerification === 'email'}
                      onChange={(e) => setForm({ ...form, email: e.target.value })}
                      className="flex-1 px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-lg text-slate-900 focus:ring-2 focus:ring-emerald-500 disabled:opacity-60"
                    />
                    <button 
                      onClick={() => handleRequestOtp('email')}
                      disabled={!isEmailChanged || isLoading || activeVerification === 'email'}
                      className={`px-4 py-2.5 text-sm font-bold rounded-lg transition-colors flex items-center ${
                        isEmailChanged && activeVerification !== 'email' 
                          ? "bg-slate-900 hover:bg-slate-800 text-white shadow-md" 
                          : "bg-slate-100 text-slate-400 cursor-not-allowed border border-slate-200"
                      }`}
                    >
                      {isLoading && activeVerification === 'email' ? <Loader2 className="h-4 w-4 animate-spin" /> : "Update"}
                    </button>
                  </div>
                  
                  {activeVerification === 'email' && (
                    <div className="mt-3 p-4 bg-emerald-50 border border-emerald-100 rounded-lg flex gap-3 animate-in fade-in slide-in-from-top-2">
                      <input
                        type="text"
                        maxLength="6"
                        placeholder="Enter 6-digit OTP"
                        value={otpCode}
                        onChange={(e) => setOtpCode(e.target.value.replace(/\D/g, ''))}
                        className="flex-1 px-4 py-2 text-center tracking-widest font-mono text-lg border border-emerald-200 rounded-md focus:ring-2 focus:ring-emerald-500"
                      />
                      <button 
                        onClick={handleVerifyOtp}
                        disabled={isLoading || otpCode.length !== 6}
                        className="px-6 py-2 bg-emerald-600 hover:bg-emerald-700 text-white font-bold rounded-md disabled:opacity-50 transition-colors"
                      >
                        {isLoading ? <Loader2 className="h-5 w-5 animate-spin mx-auto" /> : "Confirm"}
                      </button>
                    </div>
                  )}
                </div>

                <hr className="border-slate-100" />

                <div className="space-y-3">
                  <label className="block text-sm font-semibold text-slate-700">Phone Number</label>
                  <div className="flex gap-3">
                    <input
                      type="text"
                      value={form.phone}
                      disabled={activeVerification === 'phone'}
                      placeholder="+91 0000000000"
                      onChange={(e) => setForm({ ...form, phone: e.target.value })}
                      className="flex-1 px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-lg text-slate-900 focus:ring-2 focus:ring-emerald-500 disabled:opacity-60"
                    />
                    <button 
                      onClick={() => handleRequestOtp('phone')}
                      disabled={!isPhoneChanged || isLoading || activeVerification === 'phone'}
                      className={`px-4 py-2.5 text-sm font-bold rounded-lg transition-colors flex items-center ${
                        isPhoneChanged && activeVerification !== 'phone' 
                          ? "bg-slate-900 hover:bg-slate-800 text-white shadow-md" 
                          : "bg-slate-100 text-slate-400 cursor-not-allowed border border-slate-200"
                      }`}
                    >
                      {isLoading && activeVerification === 'phone' ? <Loader2 className="h-4 w-4 animate-spin" /> : "Update"}
                    </button>
                  </div>

                  {activeVerification === 'phone' && (
                    <div className="mt-3 p-4 bg-emerald-50 border border-emerald-100 rounded-lg flex gap-3 animate-in fade-in slide-in-from-top-2">
                      <input
                        type="text"
                        maxLength="6"
                        placeholder="Enter 6-digit OTP"
                        value={otpCode}
                        onChange={(e) => setOtpCode(e.target.value.replace(/\D/g, ''))}
                        className="flex-1 px-4 py-2 text-center tracking-widest font-mono text-lg border border-emerald-200 rounded-md focus:ring-2 focus:ring-emerald-500"
                      />
                      <button 
                        onClick={handleVerifyOtp}
                        disabled={isLoading || otpCode.length !== 6}
                        className="px-6 py-2 bg-emerald-600 hover:bg-emerald-700 text-white font-bold rounded-md disabled:opacity-50 transition-colors"
                      >
                        {isLoading ? <Loader2 className="h-5 w-5 animate-spin mx-auto" /> : "Confirm"}
                      </button>
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

  const ComingSoonTab = ({ title }) => (
    <div className="flex flex-col items-center justify-center h-64 bg-white rounded-2xl shadow-sm border border-slate-200 border-dashed">
      <h3 className="text-xl font-bold text-slate-700 mb-2">{title}</h3>
      <p className="text-slate-500">This module is scheduled for a future development sprint.</p>
    </div>
  );

  return (
    <div className="min-h-screen bg-slate-50 flex">
      <aside className="hidden md:flex flex-col w-64 bg-slate-900 text-slate-300 transition-all border-r border-slate-800">
        <div className="h-16 flex items-center px-6 border-b border-slate-800 bg-slate-950">
          <h1 className="text-xl font-extrabold text-white tracking-tight">RK <span className="text-emerald-500">Trendz</span></h1>
        </div>
        <div className="flex-1 overflow-y-auto py-4 px-3 space-y-1">
          {menuItems.map((item) => (
            <button
              key={item.name}
              onClick={() => setActiveTab(item.name)}
              className={`w-full flex items-center px-3 py-2.5 text-sm font-medium rounded-lg transition-all ${
                activeTab === item.name 
                  ? "bg-emerald-600 text-white shadow-md shadow-emerald-900/20" 
                  : "hover:bg-slate-800 hover:text-white"
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

      <main className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <header className="md:hidden h-16 bg-slate-900 flex items-center justify-between px-4 sm:px-6">
          <h1 className="text-lg font-bold text-white">RK <span className="text-emerald-500">Trendz</span></h1>
          <button onClick={logout} className="p-2 text-slate-400 hover:text-white"><LogOut className="h-5 w-5" /></button>
        </header>

        <div className="flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8">
          {activeTab === "Overview" && <OverviewTab />}
          {activeTab === "My Profile" && <ProfileTab />}
          {activeTab !== "Overview" && activeTab !== "My Profile" && <ComingSoonTab title={activeTab} />}
        </div>
      </main>
    </div>
  );
}
