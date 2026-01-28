import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async redirects() {
    const departments = [
      'ahuachapan', 'cabanas', 'chalatenango', 'cuscatlan',
      'la-libertad', 'la-paz', 'la-union', 'morazan',
      'san-miguel', 'san-salvador', 'san-vicente', 'santa-ana',
      'sonsonate', 'usulutan'
    ];

    return departments.flatMap(dept => [
      // Base redirect: /tag/san-salvador -> /san-salvador
      {
        source: `/tag/${dept}`,
        destination: `/${dept}`,
        permanent: true,
      },
      // Filter redirect: /tag/san-salvador/venta -> /san-salvador/venta
      {
        source: `/tag/${dept}/:filter`,
        destination: `/${dept}/:filter`,
        permanent: true,
      }
    ]);
  },
};

export default nextConfig;
