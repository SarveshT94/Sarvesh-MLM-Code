import "./globals.css"; // Ensure Tailwind is loaded!
import AuthProvider from "@/components/AuthProvider";

export const metadata = {
  title: "RK Trendz | Enterprise MLM Platform",
  description: "Advanced Multi-Level Marketing & Commission System",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      {/* antialiased makes fonts look much sharper and premium on Mac/Windows */}
      <body className="bg-slate-50 text-slate-900 antialiased">
        <AuthProvider>
          {children}
        </AuthProvider>
      </body>
    </html>
  );
}
