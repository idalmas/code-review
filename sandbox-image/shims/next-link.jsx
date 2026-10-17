export default function Link({ href, children, prefetch: _p, replace: _r, scroll: _s, ...rest }) {
  return <a href={typeof href === "string" ? href : "#"} {...rest}>{children}</a>;
}
