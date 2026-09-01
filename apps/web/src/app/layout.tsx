import type { Metadata } from "next";
import type { ReactNode } from "react";
import { AuthProvider } from "@/components/auth-provider";
import { CustomerOnboarding } from "@/components/customer-onboarding";
import { ReviewPrompt } from "@/components/review-prompt";
import { I18nProvider } from "@/components/i18n-provider";
import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "Trifecta | Mobile car care",
    template: "%s | Trifecta",
  },
  description: "Book professional mobile car care at your home or workplace.",
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en" dir="ltr" data-scroll-behavior="smooth" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: `(function(){try{var l=localStorage.getItem('trifecta-language')||(navigator.language||'en');l=l.toLowerCase().indexOf('ar')===0?'ar':'en';document.documentElement.lang=l;document.documentElement.dir=l==='ar'?'rtl':'ltr'}catch(e){}})()` }} />
      </head>
      <body><I18nProvider><AuthProvider>{children}<CustomerOnboarding /><ReviewPrompt /></AuthProvider></I18nProvider></body>
    </html>
  );
}
