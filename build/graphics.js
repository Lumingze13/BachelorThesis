/* compiled from graphics.jsx — do not edit; run `npm run build` */
(function () {
const {
  useId
} = React;
function BrandMark({
  size = 22
}) {
  return React.createElement("svg", {
    width: size,
    height: size,
    viewBox: "0 0 24 24",
    fill: "none",
    "aria-hidden": "true"
  }, React.createElement("circle", {
    cx: "12",
    cy: "12",
    r: "10.5",
    stroke: "currentColor",
    strokeOpacity: ".22",
    strokeWidth: "1"
  }), React.createElement("circle", {
    cx: "12",
    cy: "12",
    r: "6",
    stroke: "currentColor",
    strokeOpacity: ".4",
    strokeWidth: "1"
  }), React.createElement("circle", {
    cx: "12",
    cy: "12",
    r: "2.2",
    fill: "var(--accent)"
  }));
}
function Monogram({
  initials = "—",
  color = "#b5552f",
  size = 320
}) {
  return React.createElement("div", {
    className: "monogram",
    style: {
      width: size,
      height: size,
      background: color,
      fontSize: Math.round(size * 0.34)
    },
    "aria-hidden": "true"
  }, initials);
}
function MiniAvatar({
  initials,
  color,
  size = 30
}) {
  return React.createElement(Monogram, {
    initials: initials,
    color: color,
    size: size
  });
}
Object.assign(window, {
  BrandMark,
  Monogram,
  MiniAvatar
});
})();
