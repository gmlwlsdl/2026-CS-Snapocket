import type { Metadata } from "next";
import type { ReactNode } from "react";
import { Manrope, Inter } from "next/font/google";
import { ColorSchemeScript } from '@mantine/core';
import { MantineClientProvider } from '@/shared/lib/mantine/MantineClientProvider';
import { ToastProvider } from '@/shared/ui';
import { MSWProvider } from '@/shared/lib/msw/MSWProvider';
import "./globals.css";

const manrope = Manrope({
  subsets: ["latin"],
  variable: "--font-manrope",
});

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
});

export const metadata: Metadata = {
  title: "Snapocket",
  description: "The intelligence behind every lens.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html
      lang="en"
      className={`${manrope.variable} ${inter.variable} h-full antialiased`}
      suppressHydrationWarning
    >
      <head>
        <ColorSchemeScript defaultColorScheme="light" />
      </head>
      <body className="min-h-full">
        <MSWProvider>
          <MantineClientProvider>
            <ToastProvider>
              {children}
            </ToastProvider>
          </MantineClientProvider>
        </MSWProvider>
      </body>
    </html>
  );
}
