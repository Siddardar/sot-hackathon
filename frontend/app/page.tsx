import { Navbar } from "./components/Navbar";
import { Hero } from "./components/Hero";
import { HowItWorks } from "./components/HowItWorks";

export default function Home() {
  return (
    <main className="min-h-screen bg-background text-ink">
      <Navbar />
      <Hero />
      <HowItWorks />
    </main>
  );
}
