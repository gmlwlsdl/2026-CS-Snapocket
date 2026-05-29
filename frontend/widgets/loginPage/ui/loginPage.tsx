import { LoginForm } from "@/features/auth";
import { Anchor, Text } from "@mantine/core";
import { ForceLightMode } from "@/shared/ui";

export function LoginPage() {
  return (
    <ForceLightMode>
    <div className="flex min-h-screen w-full font-inter justify-center" style={{ background: 'var(--th-bg)' }}>
      <section className="flex flex-col w-full lg:w-1/2" style={{ background: 'var(--th-bg)' }}>
        <div className="flex flex-1 flex-col justify-center px-8 sm:px-16 lg:px-[100px]">
          <div className="w-full max-w-[448px] mx-auto flex flex-col gap-8">
            {/* 헤더 */}
            <div className="flex flex-col gap-2">
              <h2
                className="font-manrope font-bold"
                style={{ fontSize: 30, letterSpacing: -0.75, lineHeight: "36px", color: 'var(--th-text)' }}
              >
                Welcome back
              </h2>
              <Text c="dimmed" style={{ fontSize: 16, lineHeight: "24px" }}>
                Access your curated digital gallery.
              </Text>
            </div>

            <LoginForm />

            <Text ta="center" size="sm" c="dimmed">
              New to Snapocket?{" "}
              <Anchor href="/signup" c="snap" fw={600}>
                Create an Account
              </Anchor>
            </Text>
          </div>
        </div>

        <footer className="flex items-center justify-between px-8 sm:px-12 py-5">
          <Text size="xs" c="dimmed" style={{ letterSpacing: 1 }}>
            © 2026 Snapocket AI. The Digital Curator.
          </Text>
          <nav className="flex gap-6" aria-label="Footer links">
            {(["Privacy", "Terms", "Security"] as const).map((label) => (
              <Anchor key={label} href={`/${label.toLowerCase()}`} size="xs" c="dimmed" style={{ letterSpacing: 1 }}>
                {label}
              </Anchor>
            ))}
          </nav>
        </footer>
      </section>
    </div>
    </ForceLightMode>
  );
}
