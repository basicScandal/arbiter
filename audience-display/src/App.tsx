import { useArbiterSocket } from "./hooks/useArbiterSocket";
import { Header } from "./components/Header";
import { Footer } from "./components/Footer";
import { ScreenRouter } from "./components/ScreenRouter";

export default function App() {
  useArbiterSocket();

  return (
    <div className="flex flex-col h-screen bg-arbiter-bg font-mono">
      <Header />
      <ScreenRouter />
      <Footer />
    </div>
  );
}
