import type { Metadata } from 'next';
import LocationExplorerClient from './LocationExplorerClient';

export const metadata: Metadata = {
  title: 'Explorar por ubicación | Mapa interactivo',
  description: 'Busca una ubicación en El Salvador y explora propiedades cercanas con estadísticas de precios y listados en el mapa.',
  alternates: {
    canonical: '/explorar-por-ubicacion',
  },
};

export default function LocationExplorerPage() {
  return <LocationExplorerClient />;
}
