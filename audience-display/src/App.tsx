import { useArbiterSocket } from "./hooks/useArbiterSocket";
import { Header } from "./components/Header";
import { Footer } from "./components/Footer";
import { ScreenRouter } from "./components/ScreenRouter";
import { InjectionAlert } from "./components/InjectionAlert";
import { ViewSwitcher } from "./components/ViewSwitcher";

export default function App() {
  useArbiterSocket();

  return (
    <div className="flex flex-col h-screen bg-arbiter-bg font-mono">
      <Header />
      <ScreenRouter />
      <Footer />
      <InjectionAlert />
      <ViewSwitcher />
    </div>
  );
}
