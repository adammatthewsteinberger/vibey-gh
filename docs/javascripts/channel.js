(() => {
  "use strict";

  document.documentElement.dataset.bsTheme = "dark";

  const segments = window.location.pathname.split("/").filter(Boolean);
  const channel = segments.includes("develop") ? "develop" : "main";
  document.body.dataset.releaseChannel = channel;

  const brand = document.querySelector(".navbar-brand");
  if (brand) {
    const badge = document.createElement("span");
    badge.className = "release-badge";
    badge.innerHTML = `<span aria-hidden="true"></span>${channel === "main" ? "Production" : "Preview"}`;
    brand.insertAdjacentElement("afterend", badge);
  }

  const editLink = [...document.querySelectorAll("a.nav-link")].find((link) =>
    link.textContent.includes("Edit on GitHub"),
  );
  if (editLink) {
    editLink.href = editLink.href.replace("/edit/main/", `/edit/${channel}/`);
  }

  const footer = document.querySelector("footer.col-md-12");
  if (footer) {
    const provenance = document.createElement("p");
    provenance.className = "release-provenance";
    provenance.innerHTML = [
      `<strong>Provenance</strong>`,
      `<a href="__REPOSITORY_URL__/tree/__RELEASE_SHA__">__REPOSITORY__@__SHORT_SHA__</a>`,
      `<span>branch / __RELEASE_BRANCH__</span>`,
      `<span>channel / __RELEASE_CHANNEL__</span>`,
      `<span>Made with ❤️ by <a href="https://adammatthewsteinberger.github.io/vibey/">Vibey</a>, Developed by <a href="https://hire.adam.matthewsteinberger.com">Adam Matthew Steinberger</a></span>`,
    ].join('<span aria-hidden="true">·</span>');
    footer.append(provenance);
  }
})();
