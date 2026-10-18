import { LinkForm } from "@/components/LinkForm";
import { LoginError } from "@/components/LoginError";

export default function Home() {
  return (
    <main className="mx-auto flex w-full max-w-2xl flex-1 flex-col justify-center gap-6 px-4 py-16">
      <h1 className="text-2xl font-semibold tracking-tight">
        Open a pull request
      </h1>
      <LoginError />
      <LinkForm />
    </main>
  );
}
