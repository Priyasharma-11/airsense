import { Suspense } from "react";
import { ForecastView } from "./forecast-view";

export const metadata = { title: "Forecast" };

export default function ForecastPage() {
  return <Suspense><ForecastView /></Suspense>;
}
