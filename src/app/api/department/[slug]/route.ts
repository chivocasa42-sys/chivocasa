import { NextResponse } from 'next/server';
import { slugToDepartamento, isValidDepartamentoSlug } from '@/lib/slugify';

export async function GET(
    request: Request,
    { params }: { params: Promise<{ slug: string }> }
) {
    try {
        const { slug } = await params;

        // Validar slug
        if (!isValidDepartamentoSlug(slug)) {
            return NextResponse.json(
                { error: 'Departamento no válido' },
                { status: 404 }
            );
        }

        const departamento = slugToDepartamento(slug);

        // Llamar a la función RPC de Supabase
        const url = `${process.env.SUPABASE_URL}/rest/v1/rpc/get_scrapped_active_by_departamento`;

        const res = await fetch(url, {
            method: 'POST',
            headers: {
                'apikey': process.env.SUPABASE_SERVICE_KEY!,
                'Authorization': `Bearer ${process.env.SUPABASE_SERVICE_KEY!}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ p_departamento: departamento }),
            next: { revalidate: 300 } // Cache for 5 minutes
        });

        if (!res.ok) {
            const errorText = await res.text();
            console.error('Supabase RPC error:', errorText);
            throw new Error(`Supabase error: ${res.status}`);
        }

        const data = await res.json();

        return NextResponse.json({
            departamento,
            slug,
            count: data.length,
            listings: data
        });
    } catch (error) {
        console.error('Error fetching department listings:', error);
        return NextResponse.json(
            { error: 'Failed to fetch department listings' },
            { status: 500 }
        );
    }
}
