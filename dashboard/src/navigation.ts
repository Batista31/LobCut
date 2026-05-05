export function currentPath() {
  if (window.location.protocol === 'file:') {
    return window.location.hash.replace(/^#/, '') || '/';
  }
  return window.location.pathname;
}

export function routeHref(path: string) {
  if (window.location.protocol === 'file:') {
    return `#${path}`;
  }
  return path;
}

export function navigate(path: string) {
  window.location.href = routeHref(path);
}
