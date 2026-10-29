// Google Analytics (gtag.js). Kept in its own file because the Content-Security-Policy allows no inline scripts.
(function () {
  var id = "G-YE4L9GLC5N";
  window.dataLayer = window.dataLayer || [];
  function gtag() { window.dataLayer.push(arguments); }
  window.gtag = gtag;
  gtag("js", new Date());
  gtag("config", id);
  var s = document.createElement("script");
  s.async = true;
  s.src = "https://www.googletagmanager.com/gtag/js?id=" + id;
  document.head.appendChild(s);
})();
