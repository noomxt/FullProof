export type Theme='light'|'dark';
export const themeKey='fullproof.theme';
export function readTheme():Theme{
 try{return localStorage.getItem(themeKey)==='dark'?'dark':'light'}catch{return 'light'}
}
export function applyTheme(theme:Theme){
 document.documentElement.dataset.theme=theme;
 document.documentElement.style.colorScheme=theme;
 try{localStorage.setItem(themeKey,theme)}catch{/* Theme still works when storage is unavailable. */}
}
