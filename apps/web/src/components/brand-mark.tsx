import Image from "next/image";

export function BrandMark({ light = false }: { light?: boolean }) {
  return <Image className="brand-mark" src={light ? "/brand/trifecta-logo-light.png" : "/brand/trifecta-logo.png"} alt="" width={298} height={69} priority />;
}
