import { ProfileCard } from "@target";

const tags = ["design", "frontend", "react"];

export const states = [
  { name: "Default", render: () => <ProfileCard name="Ada Lovelace" role="Engineer" tags={tags} online /> },
  { name: "Very long name", render: () => <ProfileCard name="Maria Alejandra Fernández de la Cruz-Villanueva" role="Principal Staff Engineer, Platform Infrastructure" tags={tags} /> },
  { name: "Many tags", render: () => <ProfileCard name="Grace Hopper" role="Admiral" tags={Array.from({ length: 12 }, (_, i) => `tag-${i + 1}`)} /> },
  { name: "Empty", render: () => <ProfileCard name="" role="" tags={[]} /> },
  { name: "Phone width", viewport: { width: 360, height: 640 }, render: () => <ProfileCard name="Linus Torvalds" role="Maintainer" tags={tags} /> },
];
