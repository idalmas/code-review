export function Avatar({ name }: { name: string }) {
  const initials = name.split(" ").map((p) => p[0]).join("").slice(0, 2).toUpperCase();
  return <div className="flex h-12 w-12 items-center justify-center rounded-full bg-indigo-600 font-semibold text-white">{initials}</div>;
}
