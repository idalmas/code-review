export default function Image({ src, alt, fill: _f, priority: _p, quality: _q, placeholder: _ph, ...rest }) {
  return <img src={typeof src === "string" ? src : src?.src} alt={alt} {...rest} />;
}
