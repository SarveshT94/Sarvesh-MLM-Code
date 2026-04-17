"use client";

import { useState, useEffect } from "react";

export default function KycPage() {
    // ---- STATE MANAGEMENT ----
    const [pageStatus, setPageStatus] = useState("loading"); // loading, active, error
    const [kycStatus, setKycStatus] = useState("not_submitted"); // not_submitted, pending, approved, rejected
    const [rejectionReason, setRejectionReason] = useState("");
    const [isSubmitting, setIsSubmitting] = useState(false);
    
    const [formData, setFormData] = useState({
        pan_number: "",
        aadhar_number: "",
        bank_name: "",
        bank_account_no: "",
        bank_ifsc: ""
    });

    const [formErrors, setFormErrors] = useState({});

    // ---- FETCH INITIAL DATA ----
    useEffect(() => {
        const fetchKycStatus = async () => {
            try {
                const response = await fetch("/api/user/kyc");
                
                // 🔥 THE FIX: Handle 401 Unauthorized gracefully
                if (response.status === 401) {
                    alert("Authentication Error: You are not logged in! Please log into the backend first to establish a session cookie.");
                    setPageStatus("error");
                    return; 
                }
                
                // Handle 500 Internal Server errors gracefully
                if (response.status === 500) {
                    alert("Backend Error: Flask crashed while fetching data. Check your Python terminal for the exact error.");
                    setPageStatus("error");
                    return;
                }

                if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
                
                const result = await response.json();

                if (result.status === "success" && result.data) {
                    setKycStatus(result.data.kyc_status || "not_submitted");
                    setRejectionReason(result.data.kyc_rejection_reason || "");
                    
                    setFormData({
                        pan_number: result.data.pan_number || "",
                        aadhar_number: result.data.aadhar_number || "",
                        bank_name: result.data.bank_name || "",
                        bank_account_no: result.data.bank_account_no || "",
                        bank_ifsc: result.data.bank_ifsc || ""
                    });
                } else {
                    setKycStatus("not_submitted");
                }
                setPageStatus("active");
            } catch (error) {
                console.error("Failed to fetch KYC data:", error);
                setPageStatus("error");
            }
        };

        fetchKycStatus();
    }, []);

    // ---- INPUT HANDLING & SANITIZATION ----
    const handleChange = (e) => {
        let { name, value } = e.target;
        
        // Auto-format: PAN and IFSC must be uppercase
        if (name === "pan_number" || name === "bank_ifsc") {
            value = value.toUpperCase();
        }
        // Auto-format: Aadhar and Account No should only be numbers
        if (name === "aadhar_number" || name === "bank_account_no") {
            value = value.replace(/\D/g, ""); 
        }

        setFormData({ ...formData, [name]: value });
        
        // Clear error for this field when user starts typing
        if (formErrors[name]) {
            setFormErrors({ ...formErrors, [name]: "" });
        }
    };

    // ---- STRICT VALIDATION ENGINE ----
    const validateForm = () => {
        const errors = {};
        
        // Indian PAN Card Format: 5 Letters, 4 Digits, 1 Letter
        const panRegex = /^[A-Z]{5}[0-9]{4}[A-Z]{1}$/;
        if (!panRegex.test(formData.pan_number)) {
            errors.pan_number = "Invalid PAN format (e.g. ABCDE1234F)";
        }

        // Indian Aadhaar: Exactly 12 Digits
        if (formData.aadhar_number.length !== 12) {
            errors.aadhar_number = "Aadhaar must be exactly 12 digits";
        }

        // Bank Name: Just needs to exist
        if (formData.bank_name.trim().length < 3) {
            errors.bank_name = "Please enter a valid bank name";
        }

        // Account Number: Standard range 9 to 18 digits
        if (formData.bank_account_no.length < 9 || formData.bank_account_no.length > 18) {
            errors.bank_account_no = "Invalid account number length";
        }

        // Indian IFSC Code Format: 4 Letters, 1 Zero, 6 Alphanumeric
        const ifscRegex = /^[A-Z]{4}0[A-Z0-9]{6}$/;
        if (!ifscRegex.test(formData.bank_ifsc)) {
            errors.bank_ifsc = "Invalid IFSC format (e.g. SBIN0001234)";
        }

        setFormErrors(errors);
        return Object.keys(errors).length === 0; // Returns true if no errors
    };

    // ---- SUBMIT LOGIC ----
    const handleSubmit = async (e) => {
        e.preventDefault();
        
        if (!validateForm()) return; // Stop if validation fails
        
        setIsSubmitting(true);
        
        try {
            const response = await fetch("/api/user/kyc", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(formData)
            });
            
            // Handle unauthorized on POST as well
            if (response.status === 401) {
                alert("Your session expired. Please log in again.");
                setIsSubmitting(false);
                return;
            }

            const result = await response.json();
            
            if (result.status === "success") {
                setKycStatus("pending"); // Instantly lock the form
                window.scrollTo({ top: 0, behavior: 'smooth' });
            } else {
                alert("Error: " + result.message);
            }
        } catch (error) {
            alert("Connection failed. Ensure the backend server is running.");
        } finally {
            setIsSubmitting(false);
        }
    };

    // ---- RENDER CONDITIONS ----
    if (pageStatus === "loading") {
        return (
            <div className="max-w-4xl mx-auto my-10 p-8 animate-pulse">
                <div className="h-8 bg-gray-200 rounded w-1/3 mb-6"></div>
                <div className="h-24 bg-gray-200 rounded mb-8"></div>
                <div className="grid grid-cols-2 gap-6"><div className="h-12 bg-gray-200 rounded"></div><div className="h-12 bg-gray-200 rounded"></div></div>
            </div>
        );
    }

    if (pageStatus === "error") {
        return (
            <div className="max-w-4xl mx-auto my-10 p-8 text-center text-red-600 bg-red-50 rounded-xl border border-red-200">
                <h3 className="text-xl font-bold">Connection Error</h3>
                <p>Could not connect to the server. You may not be logged in, or the backend is offline.</p>
            </div>
        );
    }

    const isLocked = kycStatus === "approved" || kycStatus === "pending";

    return (
        <div className="max-w-4xl mx-auto my-10 p-6 md:p-10 bg-white rounded-2xl shadow-sm border border-gray-100 text-slate-800">
            
            <div className="mb-8">
                <h1 className="text-3xl font-bold text-gray-900">Account Verification</h1>
                <p className="text-gray-500 mt-2">Submit your identity and banking details to unlock withdrawals.</p>
            </div>
            
            {/* ---- DYNAMIC STATUS BANNERS ---- */}
            {kycStatus === "approved" && (
                <div className="mb-8 p-5 bg-emerald-50 text-emerald-800 border border-emerald-200 rounded-xl flex items-start gap-4">
                    <svg className="w-6 h-6 mt-1 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                    <div>
                        <h4 className="font-bold text-lg">Verification Approved</h4>
                        <p className="text-sm mt-1">Your account is fully verified. Your form has been securely locked.</p>
                    </div>
                </div>
            )}
            
            {kycStatus === "pending" && (
                <div className="mb-8 p-5 bg-amber-50 text-amber-800 border border-amber-200 rounded-xl flex items-start gap-4">
                    <svg className="w-6 h-6 mt-1 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                    <div>
                        <h4 className="font-bold text-lg">Verification in Progress</h4>
                        <p className="text-sm mt-1">Your documents are under review. This process usually takes 24-48 hours. Editing is temporarily disabled.</p>
                    </div>
                </div>
            )}
            
            {kycStatus === "rejected" && (
                <div className="mb-8 p-5 bg-red-50 text-red-800 border border-red-200 rounded-xl flex items-start gap-4">
                    <svg className="w-6 h-6 mt-1 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path></svg>
                    <div>
                        <h4 className="font-bold text-lg">Verification Rejected</h4>
                        <p className="text-sm mt-1 font-medium">Reason: {rejectionReason}</p>
                        <p className="text-sm mt-2">Please correct the details below and resubmit your application.</p>
                    </div>
                </div>
            )}

            {/* ---- KYC FORM ---- */}
            <form onSubmit={handleSubmit} className="space-y-8">
                
                {/* SECTION 1: IDENTITY */}
                <div className="bg-gray-50 p-6 rounded-xl border border-gray-100">
                    <h3 className="text-lg font-bold text-gray-800 mb-4 flex items-center gap-2">
                        <span className="bg-blue-600 text-white w-6 h-6 rounded-full flex items-center justify-center text-sm">1</span> 
                        Identity Details
                    </h3>
                    
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div>
                            <label className="block text-sm font-semibold text-gray-700 mb-2">PAN Card Number <span className="text-red-500">*</span></label>
                            <input 
                                type="text" 
                                name="pan_number" 
                                value={formData.pan_number} 
                                onChange={handleChange} 
                                readOnly={isLocked}
                                placeholder="ABCDE1234F"
                                maxLength={10}
                                className={`w-full px-4 py-3 rounded-lg border outline-none transition-all ${formErrors.pan_number ? 'border-red-500 focus:ring-2 focus:ring-red-200' : 'border-gray-300 focus:border-blue-500 focus:ring-2 focus:ring-blue-100'} ${isLocked ? 'bg-gray-200 text-gray-500 cursor-not-allowed' : 'bg-white'}`}
                            />
                            {formErrors.pan_number && <p className="text-red-500 text-xs mt-1 font-medium">{formErrors.pan_number}</p>}
                        </div>

                        <div>
                            <label className="block text-sm font-semibold text-gray-700 mb-2">Aadhaar Card Number <span className="text-red-500">*</span></label>
                            <input 
                                type="text" 
                                name="aadhar_number" 
                                value={formData.aadhar_number} 
                                onChange={handleChange} 
                                readOnly={isLocked}
                                placeholder="123456789012"
                                maxLength={12}
                                className={`w-full px-4 py-3 rounded-lg border outline-none transition-all ${formErrors.aadhar_number ? 'border-red-500 focus:ring-2 focus:ring-red-200' : 'border-gray-300 focus:border-blue-500 focus:ring-2 focus:ring-blue-100'} ${isLocked ? 'bg-gray-200 text-gray-500 cursor-not-allowed' : 'bg-white'}`}
                            />
                            {formErrors.aadhar_number && <p className="text-red-500 text-xs mt-1 font-medium">{formErrors.aadhar_number}</p>}
                        </div>
                    </div>
                </div>

                {/* SECTION 2: BANKING */}
                <div className="bg-gray-50 p-6 rounded-xl border border-gray-100">
                    <h3 className="text-lg font-bold text-gray-800 mb-4 flex items-center gap-2">
                        <span className="bg-blue-600 text-white w-6 h-6 rounded-full flex items-center justify-center text-sm">2</span> 
                        Bank Details (For Withdrawals)
                    </h3>
                    
                    <div className="space-y-6">
                        <div>
                            <label className="block text-sm font-semibold text-gray-700 mb-2">Full Bank Name <span className="text-red-500">*</span></label>
                            <input 
                                type="text" 
                                name="bank_name" 
                                value={formData.bank_name} 
                                onChange={handleChange} 
                                readOnly={isLocked}
                                placeholder="e.g. State Bank of India"
                                className={`w-full px-4 py-3 rounded-lg border outline-none transition-all ${formErrors.bank_name ? 'border-red-500 focus:ring-2 focus:ring-red-200' : 'border-gray-300 focus:border-blue-500 focus:ring-2 focus:ring-blue-100'} ${isLocked ? 'bg-gray-200 text-gray-500 cursor-not-allowed' : 'bg-white'}`}
                            />
                            {formErrors.bank_name && <p className="text-red-500 text-xs mt-1 font-medium">{formErrors.bank_name}</p>}
                        </div>

                        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                            <div>
                                <label className="block text-sm font-semibold text-gray-700 mb-2">Account Number <span className="text-red-500">*</span></label>
                                <input 
                                    type="text" 
                                    name="bank_account_no" 
                                    value={formData.bank_account_no} 
                                    onChange={handleChange} 
                                    readOnly={isLocked}
                                    placeholder="Enter your account number"
                                    maxLength={18}
                                    className={`w-full px-4 py-3 rounded-lg border outline-none transition-all ${formErrors.bank_account_no ? 'border-red-500 focus:ring-2 focus:ring-red-200' : 'border-gray-300 focus:border-blue-500 focus:ring-2 focus:ring-blue-100'} ${isLocked ? 'bg-gray-200 text-gray-500 cursor-not-allowed' : 'bg-white'}`}
                                />
                                {formErrors.bank_account_no && <p className="text-red-500 text-xs mt-1 font-medium">{formErrors.bank_account_no}</p>}
                            </div>

                            <div>
                                <label className="block text-sm font-semibold text-gray-700 mb-2">IFSC Code <span className="text-red-500">*</span></label>
                                <input 
                                    type="text" 
                                    name="bank_ifsc" 
                                    value={formData.bank_ifsc} 
                                    onChange={handleChange} 
                                    readOnly={isLocked}
                                    placeholder="SBIN0001234"
                                    maxLength={11}
                                    className={`w-full px-4 py-3 rounded-lg border outline-none transition-all ${formErrors.bank_ifsc ? 'border-red-500 focus:ring-2 focus:ring-red-200' : 'border-gray-300 focus:border-blue-500 focus:ring-2 focus:ring-blue-100'} ${isLocked ? 'bg-gray-200 text-gray-500 cursor-not-allowed' : 'bg-white'}`}
                                />
                                {formErrors.bank_ifsc && <p className="text-red-500 text-xs mt-1 font-medium">{formErrors.bank_ifsc}</p>}
                            </div>
                        </div>
                    </div>
                </div>

                {/* ---- SUBMIT BUTTON ---- */}
                {!isLocked && (
                    <div className="pt-4 border-t border-gray-100 flex justify-end">
                        <button 
                            type="submit" 
                            disabled={isSubmitting}
                            className={`px-8 py-3 rounded-lg font-bold text-white transition-all shadow-md ${isSubmitting ? 'bg-blue-400 cursor-wait' : 'bg-blue-600 hover:bg-blue-700 hover:shadow-lg active:scale-95'}`}
                        >
                            {isSubmitting ? (
                                <span className="flex items-center gap-2">
                                    <svg className="animate-spin h-5 w-5 text-white" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none"></circle><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
                                    Processing...
                                </span>
                            ) : (
                                "Submit Verification Documents"
                            )}
                        </button>
                    </div>
                )}
            </form>
        </div>
    );
}
