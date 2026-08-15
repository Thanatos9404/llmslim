import { Footer } from "@/components/landing/Footer";
import { Navbar } from "@/components/landing/Navbar";

export default function PlaygroundLayout({ children }: { children: React.ReactNode }) {
  return <div className="site-shell"><Navbar />{children}<Footer /></div>;
}
