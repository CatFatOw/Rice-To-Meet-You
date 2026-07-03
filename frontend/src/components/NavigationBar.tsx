import { Compass, FlaskConical } from "lucide-react";
import { NavLink } from "react-router-dom";

const navItems = [
  {
    name: "Explore",
    icon: Compass,
    to: "/explore",
  },
  {
    name: "Simulation",
    icon: FlaskConical,
    to: "/simulation",
  },
];

export default function Navigationbar() {
  return (
    <aside className="flex h-screen w-52 flex-col border-r border-slate-800 bg-[#050B18] text-white">
      {/* Logo */}
      <div className="border-b border-slate-800 px-4 py-5">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-linear-to-br from-orange-500 via-red-500 to-green-500">
            <span className="text-lg">🌎</span>
          </div>

          <div>
            <h1 className="text-xl font-bold">HeatSafe AI</h1>
            <p className="text-sm text-slate-400">
              FIFA World Cup 2026
            </p>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4">
        <div className="space-y-2.5">
          {navItems.map((item) => {
            const Icon = item.icon;

            return (
              <NavLink
                key={item.name}
                to={item.to}
                className={({ isActive }) =>
                  `flex w-full items-center gap-3 rounded-xl px-3 py-2.5 transition-all ${
                    isActive
                      ? "bg-blue-900/50 text-white"
                      : "text-slate-400 hover:bg-slate-900 hover:text-white"
                  }`
                }
              >
                {({ isActive }) => (
                  <>
                    <Icon
                      className={`h-4.5 w-4.5 ${isActive ? "text-blue-400" : ""}`}
                    />
                    <span className="text-base font-medium">{item.name}</span>
                  </>
                )}
              </NavLink>
            );
          })}
        </div>
      </nav>
    </aside>
  );
}