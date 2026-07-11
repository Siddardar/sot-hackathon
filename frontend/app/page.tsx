import { Navbar } from "./components/Navbar";
import { Hero } from "./components/Hero";
import { HowItWorks } from "./components/HowItWorks";
import { FAQ } from "./components/FAQ";

export default function Home() {
  return (
    <main className="min-h-screen text-ink">
      <Navbar />
      <Hero />
      <HowItWorks />
      <FAQ />
    </main>
  );
}
