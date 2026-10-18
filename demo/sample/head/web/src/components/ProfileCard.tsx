import { Avatar } from "@/components/Avatar";

export interface ProfileCardProps {
  name: string;
  role: string;
  tags: string[];
  online?: boolean;
}

export function ProfileCard({ name, role, tags, online = false }: ProfileCardProps) {
  return (
    <div className="flex w-80 items-start gap-4 rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
      <div className="relative">
        <Avatar name={name} />
        {online && <span className="absolute -right-0.5 -bottom-0.5 h-3.5 w-3.5 rounded-full border-2 border-white bg-green-500" />}
      </div>
      <div>
        <h3 className="whitespace-nowrap font-semibold text-gray-900">{name}</h3>
        <p className="text-sm text-gray-500">{role}</p>
        <div className="mt-2 flex gap-1">
          {tags.map((t) => (
            <span key={t} className="rounded-full bg-indigo-50 px-2 py-0.5 text-xs text-indigo-700">{t}</span>
          ))}
        </div>
      </div>
    </div>
  );
}
