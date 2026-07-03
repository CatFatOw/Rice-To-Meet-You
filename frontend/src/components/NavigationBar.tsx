import { Compass, FlaskConical } from "lucide-react";

const navItems = [
  {
    name: "Explore",
    icon: Compass,
    active: true,
  },
  {
    name: "Simulation",
    icon: FlaskConical,
    active: false,
  },
];

export default function Navigationbar() {
  return (
    <aside className="flex h-screen w-64 flex-col border-r border-slate-800 bg-[#050B18] text-white">
      {/* Logo */}
      <div className="border-b border-slate-800 px-6 py-6">
        <div className="flex items-center gap-3">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-linear-to-br from-orange-500 via-red-500 to-green-500">
            <span className="text-xl">🌎</span>
          </div>

          <div>
            <h1 className="text-2xl font-bold">HeatSafe AI</h1>
            <p className="text-base text-slate-400">
              FIFA World Cup 2026
            </p>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-4 py-5">
        <div className="space-y-2.5">
          {navItems.map((item) => {
            const Icon = item.icon;

            return (
              <button
                key={item.name}
                className={`flex w-full items-center gap-3 rounded-xl px-4 py-3 transition-all ${
                  item.active
                    ? "bg-blue-900/50 text-white"
                    : "text-slate-400 hover:bg-slate-900 hover:text-white"
                }`}
              >
                <Icon
                  className={`h-5 w-5 ${
                    item.active ? "text-blue-400" : ""
                  }`}
                />

                <span className="text-lg font-medium">
                  {item.name}
                </span>
              </button>
            );
          })}
        </div>
      </nav>
    </aside>
  );
}