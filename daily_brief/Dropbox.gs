/*** Dropbox -> Daily Brief integration (PASTE THIS VERSION) ================
 * Add as a NEW script file (name it "Dropbox") in the "Shorts Creation Daily
 * Brief" Apps Script project. Then make ONE change in Code.gs (see bottom).
 *
 * Credentials live in Script Properties (Project Settings -> Script Properties):
 *   DROPBOX_APP_KEY / DROPBOX_APP_SECRET / DROPBOX_REFRESH_TOKEN
 * Once those are set, the brief auto-pulls live counts every morning.
 * Run dropboxDryRun() any time to see client<->folder matches.
 * ==========================================================================*/

const DROPBOX = {
  rootPath: '', // '' = Dropbox root. If client folders live in a subfolder, set e.g. '/Clients'
  videoExts: ['mp4', 'mov', 'm4v', 'avi', 'mkv', 'webm', 'mts'],
  buckets: [ // subfolder name -> bucket, checked IN ORDER (first match wins)
    { bucket: 'posted', match: ['posted', 'published', 'uploaded', 'done'] },
    { bucket: 'final', match: ['final', 'edited', 'ready to post', 'approved', 'ready'] },
    { bucket: 'raw', match: ['raw', 'footage', 'to edit', 'unedited'] },
    { bucket: 'review', match: ['review', 'to review', 'approval'] },
  ],
  // Hard overrides for clients whose Dropbox folder name doesn't fuzzy-match.
  // `client` is a normalized fragment of the client name; `folder` is the EXACT Dropbox folder.
  aliases: [
    { client: 'eileen pineiro',   folder: 'Elieen Pineiro' },        // Dropbox folder is misspelled "Elieen"
    { client: 'frank mata',       folder: 'Frank (Yacht Charter)' },
    { client: 'secure funding',   folder: 'Secured Funding Content' },
    { client: 'pgl',              folder: 'Paul Capote Content' },    // PGL Landscaping = Paul Capote
    { client: 'concrete designs', folder: 'Manny Mollinedo' },        // Concrete Designs = Manny Mollinedo
  ],
  custom: {
    'Concrete Designs': {
      root: '/Manny Mollinedo/@ConcreteDesignsLLC/Videos',
      label: '@ConcreteDesignsLLC/Videos',
      review: { sub: '2. Videos To Review' },
      final: { sub: '3. Final Edited Videos', month: true },
    },
    'Manny Personal Reels': {
      root: '/Manny Mollinedo/@MannyMollinedo/Personal Reels',
      label: 'Personal Reels',
      final: { sub: '2. Edited Videos Reels', month: true },
    },
  },
  extraClients: [
    { name: 'Manny Personal Reels', priority: 'normal', editor: 'Confirm', status: 'Active', action: 'Check this month edited personal reels.' },
  ],
  P: { key: 'DROPBOX_APP_KEY', secret: 'DROPBOX_APP_SECRET', refresh: 'DROPBOX_REFRESH_TOKEN' },
};

function dropboxSaveAppCreds() {
  const p = PropertiesService.getScriptProperties();
  p.setProperty(DROPBOX.P.key, '4jk585qv4azpxoc');
  p.setProperty(DROPBOX.P.secret, 'mintzh6pthvccko');
  Logger.log('Saved Dropbox app key + secret. Next: run dropboxAuthStart().');
}

function dropboxAuthStart() {
  const key = PropertiesService.getScriptProperties().getProperty(DROPBOX.P.key);
  Logger.log('Open this, approve, COPY THE CODE, then paste it into dropboxConnect():\n\n' +
    'https://www.dropbox.com/oauth2/authorize?client_id=' + key +
    '&token_access_type=offline&response_type=code');
}

function dropboxConnect() {
  // 1) Run dropboxAuthStart() first; approve; copy the code Dropbox shows.
  // 2) Paste that code between the quotes below, SAVE, then Run this function.
  const CODE = 'PASTE_CODE_HERE';

  const p = PropertiesService.getScriptProperties();
  const res = UrlFetchApp.fetch('https://api.dropboxapi.com/oauth2/token', {
    method: 'post', muteHttpExceptions: true,
    payload: { code: CODE, grant_type: 'authorization_code',
      client_id: p.getProperty(DROPBOX.P.key), client_secret: p.getProperty(DROPBOX.P.secret) },
  });
  const data = JSON.parse(res.getContentText());
  if (!data.refresh_token) { Logger.log('FAILED (code may be expired — re-run dropboxAuthStart): ' + res.getContentText()); return; }
  p.setProperty(DROPBOX.P.refresh, data.refresh_token);
  Logger.log('Connected! Refresh token stored. Next: run dropboxDryRun().');
}

function dropboxAccessToken_() {
  const p = PropertiesService.getScriptProperties();
  const res = UrlFetchApp.fetch('https://api.dropboxapi.com/oauth2/token', {
    method: 'post', muteHttpExceptions: true,
    payload: { grant_type: 'refresh_token', refresh_token: p.getProperty(DROPBOX.P.refresh),
      client_id: p.getProperty(DROPBOX.P.key), client_secret: p.getProperty(DROPBOX.P.secret) },
  });
  const data = JSON.parse(res.getContentText());
  if (!data.access_token) throw new Error('Dropbox refresh failed: ' + res.getContentText());
  return data.access_token;
}

function dbxList_(token, path) {
  const out = [];
  let res = JSON.parse(UrlFetchApp.fetch('https://api.dropboxapi.com/2/files/list_folder', {
    method: 'post', contentType: 'application/json', headers: { Authorization: 'Bearer ' + token },
    muteHttpExceptions: true, payload: JSON.stringify({ path: path || '', recursive: false, limit: 2000 }),
  }).getContentText());
  if (res.error_summary) throw new Error('list_folder: ' + res.error_summary + ' (path "' + path + '")');
  out.push.apply(out, res.entries || []);
  while (res.has_more) {
    res = JSON.parse(UrlFetchApp.fetch('https://api.dropboxapi.com/2/files/list_folder/continue', {
      method: 'post', contentType: 'application/json', headers: { Authorization: 'Bearer ' + token },
      muteHttpExceptions: true, payload: JSON.stringify({ cursor: res.cursor }),
    }).getContentText());
    out.push.apply(out, res.entries || []);
  }
  return out;
}

function dbxNorm_(s) { return String(s).toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim(); }

function dbxMatchFolder_(folders, clientName) {
  // Alias overrides first — handle renamed/misspelled folders.
  const cn = dbxNorm_(clientName);
  for (const a of (DROPBOX.aliases || [])) {
    if (cn.indexOf(dbxNorm_(a.client)) !== -1 && folders.indexOf(a.folder) !== -1) return a.folder;
  }
  const terms = clientName.split('/').map(dbxNorm_).filter(t => t.length > 2);
  terms.push(dbxNorm_(clientName));
  let best = null, bestScore = 1e9;
  folders.forEach(f => {
    const fn = dbxNorm_(f);
    terms.forEach(t => {
      if (fn === t || fn.indexOf(t) !== -1 || t.indexOf(fn) !== -1) {
        const score = Math.abs(fn.length - t.length);
        if (score < bestScore) { best = f; bestScore = score; }
      }
    });
  });
  return best;
}

function dbxBucket_(name) {
  const n = dbxNorm_(name);
  for (const r of DROPBOX.buckets) if (r.match.some(m => n.indexOf(dbxNorm_(m)) !== -1)) return r.bucket;
  return null;
}

function dbxIsVideo_(name) { return DROPBOX.videoExts.indexOf((name.split('.').pop() || '').toLowerCase()) !== -1; }

function dropboxClientCounts_() {
  const token = dropboxAccessToken_();
  const folders = dbxList_(token, DROPBOX.rootPath).filter(e => e['.tag'] === 'folder').map(e => e.name);
  const counts = {}, unmatched = folders.slice();

  Object.keys(DROPBOX.custom || {}).forEach(name => {
    counts[name] = dropboxCustomCount_(token, DROPBOX.custom[name]);
    const top = DROPBOX.custom[name].root.split('/').filter(Boolean)[0];
    const ui = unmatched.indexOf(top); if (ui >= 0) unmatched.splice(ui, 1);
  });
  CLIENTS.forEach(c => {
    if (counts[c.name]) return;
    const folder = dbxMatchFolder_(folders, c.name);
    if (!folder) return;
    const i = unmatched.indexOf(folder); if (i >= 0) unmatched.splice(i, 1);
    const tally = { raw: 0, review: 0, final: 0, posted: 0 };
    const base = (DROPBOX.rootPath || '') + '/' + folder;
    dbxList_(token, base).filter(e => e['.tag'] === 'folder').forEach(sub => {
      const bucket = dbxBucket_(sub.name); if (!bucket) return;
      tally[bucket] += dbxCountVideosUnder_(token, base + '/' + sub.name);
    });
    counts[c.name] = Object.assign({ folder: folder }, tally);
  });
  counts.__unmatched = unmatched;
  return counts;
}

function dropboxDryRun() {
  const counts = dropboxClientCounts_();
  Logger.log('===== CLIENT -> FOLDER MATCHES =====');
  [].concat(CLIENTS.map(c => c.name), (DROPBOX.extraClients || []).map(c => c.name)).forEach(nm => {
    const c = { name: nm };
    const m = counts[c.name];
    Logger.log(m ? c.name + ' -> [' + m.folder + '] Review ' + m.review + ' / Final ' + m.final + ' / Posted ' + m.posted
      : c.name + ' -> (NO MATCH)');
  });
  Logger.log('\n===== DROPBOX FOLDERS NOT MATCHED TO A CLIENT =====');
  (counts.__unmatched || []).forEach(f => Logger.log(' - ' + f));
}

function applyDropboxCounts_(clients) {
  try {
    const counts = dropboxClientCounts_();
    clients.forEach(c => {
      const m = counts[c.name];
      if (m) { c.raw = m.raw; c.review = m.review; c.final = m.final; c.posted = m.posted; }
    });
    (DROPBOX.extraClients || []).forEach(ec => {
      if (clients.some(c => c.name === ec.name)) return;
      const m = counts[ec.name] || { raw: 0, review: 0, final: 0, posted: 0 };
      clients.push(Object.assign({}, ec, { raw: m.raw, review: m.review, final: m.final, posted: m.posted }));
    });
  } catch (e) { Logger.log('Dropbox counts skipped: ' + e.message); }
  return clients;
}

/* ===== ONE CHANGE IN Code.gs =============================================
 * In sendDailyBrief(), find: const clients = getClients_();
 * change it to: const clients = applyDropboxCounts_(getClients_());
 * ========================================================================*/


function dbxListRecursive_(token, path) {
  const out = [];
  let res = JSON.parse(UrlFetchApp.fetch('https://api.dropboxapi.com/2/files/list_folder', {
    method: 'post', contentType: 'application/json', headers: { Authorization: 'Bearer ' + token },
    muteHttpExceptions: true, payload: JSON.stringify({ path: path || '', recursive: true, limit: 2000 }),
  }).getContentText());
  if (res.error_summary) return out;
  out.push.apply(out, res.entries || []);
  while (res.has_more) {
    res = JSON.parse(UrlFetchApp.fetch('https://api.dropboxapi.com/2/files/list_folder/continue', {
      method: 'post', contentType: 'application/json', headers: { Authorization: 'Bearer ' + token },
      muteHttpExceptions: true, payload: JSON.stringify({ cursor: res.cursor }),
    }).getContentText());
    out.push.apply(out, res.entries || []);
  }
  return out;
}
function dbxCountVideosUnder_(token, path) {
  return dbxListRecursive_(token, path).filter(e => e['.tag'] === 'file' && dbxIsVideo_(e.name)).length;
}
function dbxCurrentMonthFolder_(token, basePath) {
  const tz = (typeof CONFIG !== 'undefined' && CONFIG.timezone) ? CONFIG.timezone : 'America/New_York';
  const monthName = dbxNorm_(Utilities.formatDate(new Date(), tz, 'MMMM'));
  let subs;
  try { subs = dbxList_(token, basePath).filter(e => e['.tag'] === 'folder'); } catch (e) { return null; }
  const hit = subs.find(s => dbxNorm_(s.name).indexOf(monthName) !== -1);
  return hit ? basePath + '/' + hit.name : null;
}
function dropboxCustomCount_(token, cfg) {
  const tally = { raw: 0, review: 0, final: 0, posted: 0, folder: cfg.label || cfg.root };
  ['raw', 'review', 'final', 'posted'].forEach(b => {
    const spec = cfg[b]; if (!spec) return;
    let p = cfg.root + '/' + spec.sub;
    if (spec.month) p = dbxCurrentMonthFolder_(token, p);
    if (p) tally[b] = dbxCountVideosUnder_(token, p);
  });
  return tally;
}
