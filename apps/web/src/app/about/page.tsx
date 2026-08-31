import type { Metadata } from "next";
import { AboutPage } from "@/components/about-page";

export const metadata: Metadata = {
  title: {
    absolute: "About Trifecta | Mobile Car Washing & Detailing Abu Dhabi",
  },
  description: "Meet Trifecta, providing mobile vehicle care in Abu Dhabi for individual customers and corporate, facility, and property partnerships.",
};

export default function Page() {
  return <AboutPage />;
}
