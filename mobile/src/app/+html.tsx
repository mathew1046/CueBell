import { ScrollViewStyleReset, useServerDocumentContext } from 'expo-router/html';
import type { PropsWithChildren } from 'react';

export default function Html({ children }: PropsWithChildren) {
  const { headNodes, bodyNodes, htmlAttributes, bodyAttributes } = useServerDocumentContext();
  return <html lang="en" {...htmlAttributes}>
    <head>
      <meta charSet="utf-8" />
      <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
      <meta name="theme-color" content="#F8F5F4" />
      <meta name="description" content="CueBell turns spoken announcements into personal visual alerts, live captions, vibration and sound." />
      <meta name="apple-mobile-web-app-capable" content="yes" />
      <link rel="manifest" href="/manifest.webmanifest" />
      <link rel="apple-touch-icon" href="/icons/icon-192.png" />
      <ScrollViewStyleReset />
      <style>{`:focus-visible { outline: 3px solid currentColor; outline-offset: 3px; }
        html, body { background: #F8F5F4; }
        @media (prefers-color-scheme: dark) { html, body { background: #161818; } }
        @media (forced-colors: active) { canvas { forced-color-adjust: none; } }`}</style>
      {headNodes}
    </head>
    <body {...bodyAttributes}>{children}{bodyNodes}</body>
  </html>;
}
