import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "OCR Lake",
  description: "이미지에서 텍스트를 추출하고 처리 이력을 조회합니다.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body>
        <header className="site-header">
          <nav aria-label="주요 메뉴">
            <a href="/" className="brand">
              OCR Lake
            </a>
            <a href="/records">처리 이력</a>
          </nav>
        </header>
        <main>{children}</main>
      </body>
    </html>
  );
}
