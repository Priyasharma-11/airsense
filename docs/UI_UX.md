# UI/UX Design Specification

**Direction:** an environmental-intelligence SaaS that is calm and information-dense. One brand hue (atmospheric teal), and colour elsewhere is reserved
for meaning: the AQI categories and the forecast band. Dark-first marketing surfaces; app in light and dark.

## Design tokens (`frontend/src/app/globals.css`)
| Token group | Values |
|---|---|
| Surfaces | `bg` #f6f8fa / #070d16 · `elevated` #fff / #0d1622 · `subtle` · `inset` |
| Text | `fg` #0b1726 / #e8eef5 · `muted` · `faint` |
| Brand | teal 50–700 (`brand-500` #12b89a, `brand-600` #0a9480) · accent #3b82f6 |
| Feedback | success #16a34a · warning #d97706 · danger #dc2626 |
| AQI (CPCB) | Good #2e9e5b · Satisfactory #8fbf3f · Moderate #e5b53a · Poor #ee8a3c · Very Poor #e04f4f · Severe #8e2c48 |
| Typography | Sora (display: 600 weight, tight tracking) + Inter (UI, `cv11`/`ss01`, tabular numerals for data) · scale 11.5 / 12.5 / 13.5 / 15 / 18 / 24 / 28 / 36 / 56 px |
| Spacing | 4-px base; cards use 20 px padding (`px-5`); 16 px grid gaps |
| Radius | 6 · 10 (controls) · 14 · 16 (cards) · 20 (dialogs) · 28 (hero CTA) |
| Shadows | `shadow-card` (1 + 16 px soft) · `shadow-pop` (dialogs, hover) |
| Focus | 3 px teal ring on `:focus-visible` everywhere |

## Components (`src/components/ui`)
Button (primary / secondary / outline / ghost / danger; sm / md / lg; loading state) · Card + CardHeader (icon, subtitle, action slot, wraps on narrow screens) ·
Badge (6 tones) and AqiBadge (category colour, tinted background) · Input / Select / Field (label, hint, error with `role=alert`) · Toggle (`role=switch`) ·
Segmented control (`role=radiogroup`) · Stat tile (accent strip) · Skeleton and ChartSkeleton (shimmer, `prefers-reduced-motion` respected) ·
ErrorState (message, request id, retry) · EmptyState (icon, guidance, CTA) · ConfirmDialog (Radix Dialog, focus trap, Framer Motion) · Toasts (Sonner, themed).

## Charts (ECharts, tree-shaken)
Theme-aware tokens via `useChartTokens()`: muted axes, 7%-opacity grid, rounded tooltips, one 10-colour categorical palette, a brand-tinted interval band,
a red dashed threshold line, and IST time labels. Every chart has `role="img"` and a descriptive `aria-label`. Missing data is drawn as gaps, never interpolated.

## Pages
| Page | Purpose and key UI |
|---|---|
| Landing `/` | Dark hero with a live station pill, live forecast preview card, network ticker, capabilities grid, pipeline steps with live accuracy figures, CTA, footer |
| Auth `/login` `/register` `/forgot-password` `/reset-password` | Split layout with a live "most polluted now" panel, inline validation, password rule chips |
| Overview `/dashboard` | AQI gauge + health advice + scale, 4 stat tiles, 7 d + 24 h chart, pollutants, conditions, network table with sparklines, recent alerts |
| Analytics `/analytics` | Filter bar (pollutant, period, stations), insight cards, 8 chart cards |
| Forecast `/forecast` | Station picker (URL-synced), 4 KPIs including the cleanest window, forecast and interval chart, threshold + horizon controls, exceedance bars, SHAP contributions, hourly table |
| Model Lab `/models` | KPIs, error-by-horizon (MAE/RMSE/R²), importance, actual vs predicted, residuals, alerting precision/recall, comparison table, SARIMA note |
| Geospatial `/map` | Leaflet map (current / hotspot layer, OSM tiles, dark filter), nearest-to-me, hotspot ranking, method note, selection card |
| Alerts `/alerts` | New-rule form, rule list (pause/delete with confirmation), history with filter, pagination, read/delete |
| Settings `/settings` | Preferences, theme, profile, password, delete account (type-to-confirm) |
| Methodology `/methodology` | Live sources, cleaning rules, features, models, uncertainty, hotspots, limitations, with a sticky TOC |

## Responsiveness and accessibility
Breakpoints: `sm` 640 · `md` 768 · `lg` 1024 (sidebar appears) · `xl` 1280 (multi-column grids). Mobile uses a slide-in drawer. Tables scroll horizontally inside their card.
E2E verifies there is no horizontal page overflow on a Pixel 7 viewport. There is a skip link and visible focus, every control is labelled, the colour of AQI is always paired with a text label, and motion is reduced for users who ask.
