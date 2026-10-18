import { Avatar } from "@/components/Avatar";

export interface ProfileCardProps {
  name: string;
  role: string;
  tags: string[];
}

export function ProfileCard({ name, role, tags }: ProfileCardProps) {
  return (
    <div className="flex w-80 items-start gap-4 rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
      <Avatar name={name} />
      <div className="min-w-0">
        <h3 className="truncate font-semibold text-gray-900">{name}</h3>
        <p className="text-sm text-gray-500">{role}</p>
        <div className="mt-2 flex flex-wrap gap-1">
          {tags.map((t) => (
            <span key={t} className="rounded bg-gray-100 px-2 py-0.5 text-xs text-gray-700">{t}</span>
          ))}
        </div>
      </div>
    </div>
  );
}
