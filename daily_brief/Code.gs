const CONFIG = {
  timezone: 'America/New_York',
  sendHour: 8,
  recipientEmail: Session.getActiveUser().getEmail(),
  calendarEventTitle: 'Shorts Creation Daily Brief',
  createCalendarBlock: true,
  calendarBlockMinutes: 30,
  businessName: 'Shorts Creation',
  memoryKey: 'shorts_creation_daily_brief_memory',
  memoryLookbackDays: 30,
  maxArticleAgeHours: 96,    // 4 days max; we strongly prefer the last 48h
  articlesToShow: 3,         // how many news articles + news-driven video ideas

  // OPTIONAL: paste an Anthropic key in Project Settings -> Script Properties as
  // ANTHROPIC_API_KEY to get sharper, article-specific context/hook/body/caption.
  // Without it, the brief STILL writes a full hook/body/cut/caption from each
  // article's own summary -- it just uses smart templates instead of the model.
  claudeModel: 'claude-haiku-4-5-20251001', // cheap + fast. Swap to 'claude-sonnet-4-6' for higher quality.
  instagramHandle: '@shortscreation',

  // Optional later: paste a Google Sheet ID here with columns:
  // Client, Status, Raw, Review, Final, Posted, Editor, Action, Priority
  clientSheetId: '',
};

const CLIENTS = [
  { name: 'Concrete Designs', priority: 'high', editor: 'Confirm', status: 'Active', action: 'Check raw footage, review queue, and next approved post.' },
  { name: 'PGL Landscaping', priority: 'normal', editor: 'Confirm', status: 'Active', action: 'Check pipeline count and next landscaping post.' },
  { name: 'Jonathan Roofing Company', priority: 'normal', editor: 'Confirm', status: 'Active', action: 'Confirm next roofing proof/educational video.' },
  { name: 'Jason Valdes', priority: 'normal', editor: 'Confirm', status: 'Active', action: 'Check next deliverable and review status.' },
  { name: 'Frank Mata / Miami Vice Charters', priority: 'normal', editor: 'Confirm', status: 'Active', action: 'Look for yacht/BTS footage ready to turn around.' },
  { name: 'Roger Chirino / Chirino USA Accountants', priority: 'normal', editor: 'Confirm', status: 'Active', action: 'Check tax/accounting content queue.' },
  { name: 'Cristian J De Paz / Secure Funding Pros', priority: 'normal', editor: 'Confirm', status: 'Active', action: 'Check funding/credit content pipeline.' },
  { name: 'Jose Gonzalez / Podium Industry', priority: 'normal', editor: 'Confirm', status: 'Active', action: 'Confirm next edited post and raw backlog.' },
  { name: 'Averity Insurance', priority: 'normal', editor: 'Confirm', status: 'Active', action: 'Check insurance education content queue.' },
  { name: 'Angel Rodriguez', priority: 'normal', editor: 'Confirm', status: 'Active', action: 'Check next client-facing deliverable.' },
  { name: 'PSI Security', priority: 'normal', editor: 'Confirm', status: 'Active', action: 'Check security content queue.' },
  { name: 'Fabrizio / Real Estate', priority: 'normal', editor: 'Confirm', status: 'Active', action: 'Check listing/realtor content queue.' },
  { name: 'Ruben Cedano', priority: 'normal', editor: 'Confirm', status: 'Active', action: 'Check current status and next post.' },
  { name: 'Eileen Pineiro', priority: 'normal', editor: 'Confirm', status: 'Onboarding', action: 'Confirm onboarding items and first content direction.' },
  { name: 'Diana Santos', priority: 'normal', editor: 'Confirm', status: 'Active', action: 'Check current pipeline status.' },
  { name: 'Daniel / Dynamic Auto', priority: 'normal', editor: 'Confirm', status: 'Active', action: 'Check auto content queue.' },
  { name: 'Lazaro / Rogue Drywall', priority: 'normal', editor: 'Confirm', status: 'Active', action: 'Check drywall project footage and next post.' },
];

// ===========================================================================
// NEWS SOURCES
// Real publisher RSS feeds. These give a DIRECT article link + a real summary
// we can actually use as context -- unlike Google News, whose links are
// redirect URLs with no usable description. Any feed that errors is skipped.
// ===========================================================================
const NEWS_FEEDS = [
  { source: 'Social Media Today', url: 'https://www.socialmediatoday.com/feeds/news/' },
  { source: 'Search Engine Journal', url: 'https://www.searchenginejournal.com/category/social-media/feed/' },
  { source: 'Later', url: 'https://later.com/blog/rss/' },
  { source: 'Buffer', url: 'https://buffer.com/resources/rss/' },
  { source: 'Hootsuite', url: 'https://blog.hootsuite.com/feed/' },
  { source: 'Sprout Social', url: 'https://sproutsocial.com/insights/feed/' },
  { source: 'Tubefilter', url: 'https://www.tubefilter.com/feed/' },
  { source: 'TechCrunch', url: 'https://techcrunch.com/tag/social/feed/' },
  { source: 'The Verge', url: 'https://www.theverge.com/rss/index.xml' },
  { source: 'TikTok Newsroom', url: 'https://newsroom.tiktok.com/en-us/rss' },
  { source: 'YouTube Blog', url: 'https://blog.youtube/rss/' },
];

// Google News fallback queries. Only used to fill empty slots if the publisher
// feeds come up short. when:3d keeps it current.
const NEWS_QUERIES = [
  'Instagram Reels update creators when:4d',
  'TikTok creators new feature when:4d',
  'YouTube Shorts update creators when:4d',
  'Instagram algorithm reach engagement tips when:5d',
  'short form video marketing small business when:5d',
];

// ---- Topic vocabulary used for scoring -----------------------------------
const PLATFORM_TERMS = [
  'instagram', 'reels', 'reel', 'tiktok', 'youtube', 'shorts', 'threads', 'meta', 'facebook',
];

const INDUSTRY_TERMS = [
  'instagram', 'reels', 'tiktok', 'youtube', 'shorts', 'threads', 'meta', 'creator', 'creators',
  'content', 'social media', 'short form', 'short-form', 'video', 'ugc', 'influencer', 'capcut', 'editing',
];

// Actionable / "something changed" signals -- the stuff worth talking about.
const ACTIONABLE_TERMS = [
  'how to', 'tips', 'tip', 'strategy', 'strategies', 'guide', 'playbook', 'tutorial', 'best practice',
  'update', 'updates', 'new feature', 'feature', 'launches', 'launch', 'rolls out', 'rolling out',
  'announces', 'announced', 'introduces', 'adds', 'now lets', 'you can now', 'change', 'changes',
];

// Growth / get-seen / make-better-videos signals (what the user cares about).
const GROWTH_TERMS = [
  'algorithm', 'reach', 'engagement', 'views', 'grow', 'growth', 'audience', 'retention',
  'watch time', 'discoverability', 'seo', 'hashtag', 'hashtags', 'trend', 'trending',
  'monetization', 'monetize', 'content strategy', 'hook', 'hooks', 'caption', 'captions',
  'followers', 'subscribers', 'collab', 'collaboration', 'analytics', 'insights',
];

const TRUSTED_NEWS_SOURCES = [
  'Social Media Today', 'Search Engine Journal', 'Search Engine Land', 'Marketing Dive',
  'Adweek', 'Digiday', 'HubSpot', 'Sprout Social', 'Buffer', 'Later', 'Hootsuite',
  'Tubefilter', 'The Verge', 'TechCrunch', 'Mashable', 'Meta', 'Instagram', 'TikTok',
  'YouTube', 'Google', 'Metricool',
];

const LOCAL_TARGET_TERMS = [
  'miami', 'south florida', 'florida', 'fort lauderdale', 'broward', 'palm beach',
  'united states', 'small business', 'business owner', 'local business',
];

// ===========================================================================
// HARD KILL LISTS -- these guarantee junk like "buy Instagram followers",
// "best sites to buy followers", and spammy affiliate listicles NEVER appear.
// ===========================================================================
const SPAM_BLOCKLIST = [
  'buy followers', 'buy instagram', 'buy tiktok', 'buy youtube', 'buy real', 'buy active',
  'buy views', 'buy likes', 'buy subscribers', 'buy comments', 'best sites to buy',
  'best site to buy', 'sites to buy', 'site to buy', 'where to buy', 'place to buy',
  'free followers', 'get free followers', 'followers free', 'followers fast', 'followers instantly',
  'grow followers fast', 'increase followers', 'gain followers', 'more followers fast',
  'smm panel', 'smm service', 'follower service', 'growth service', 'cheap followers',
  'real active followers', 'followers app', 'followers in 2025', 'followers in 2026',
  'best apps to', 'top apps to', 'best tools to buy', 'best panel',
  'affiliate marketing', 'coupon', 'promo code', 'discount code', 'giveaway', 'sweepstakes',
  'casino', 'crypto', 'bitcoin', 'forex', 'make money online', 'side hustle', 'passive income',
  'get rich', 'best vpn', 'best proxy', 'review 2026', 'review 2025',
];

// Clearly off-industry / noise / doom news the brief should ignore.
const OFFTOPIC_BLOCKLIST = [
  'cricket', 'premier league', 'k-pop', 'grand prix', 'indycar', 'nascar', 'formula 1',
  'box office', 'movie review', 'recipe', 'horoscope', 'onlyfans', 'dating app',
  'south africa', 'nigeria', 'pakistan', 'bangladesh', 'sri lanka', 'kenya', 'ghana',
  'latest jobs', 'jobs in', 'job opening', 'hiring near', 'sweepstake',
  'lawsuit', 'sued', 'arrested', 'indicted', 'shooting', 'killed', 'obituary', 'dies at',
];

function setupDailyBrief() {
  deleteDailyBriefTriggers_();
  ScriptApp.newTrigger('sendDailyBrief')
    .timeBased()
    .everyDays(1)
    .atHour(CONFIG.sendHour)
    .nearMinute(0)
    .inTimezone(CONFIG.timezone)
    .create();
  sendDailyBrief();
}

function resetBriefMemory() {
  PropertiesService.getScriptProperties().deleteProperty(CONFIG.memoryKey);
}

function debugNewsSelection() {
  const articles = getNewsArticles_({ articles: [], ideas: [], runs: [], picked: [] });
  articles.forEach(article => {
    Logger.log(`${article.score} | ${article.source} | sum:${usableSummary_(article.summary) ? 'Y' : 'n'} | ${article.title}`);
  });
}

function sendDailyBrief() {
  const now = new Date();
  const today = startOfDay_(now);
  const tomorrow = addDays_(today, 1);
  const dateLabel = Utilities.formatDate(today, CONFIG.timezone, 'EEEE, MMMM d, yyyy');

  const memory = loadMemory_();
  const calendarEvents = getTodaysCalendar_(today, tomorrow);
  const clients = applyDropboxCounts_(getClients_());
  const articles = getNewsArticles_(memory);
  const videoIdeas = buildVideoIdeas_(articles, clients, calendarEvents, memory);
  const mainThings = buildMainThings_(calendarEvents, clients, articles);
  const briefText = buildPlainTextBrief_(dateLabel, mainThings, calendarEvents, clients, articles, videoIdeas, memory);
  const briefHtml = buildHtmlBrief_(dateLabel, mainThings, calendarEvents, clients, articles, videoIdeas, memory);

  GmailApp.sendEmail(
    CONFIG.recipientEmail,
    `${CONFIG.businessName} Daily Brief - ${dateLabel}`,
    briefText,
    { htmlBody: briefHtml, name: `${CONFIG.businessName} Brief` }
  );

  if (CONFIG.createCalendarBlock) {
    upsertCalendarBlock_(today, briefText);
  }

  rememberRun_(memory, dateLabel, articles, videoIdeas);
}

function deleteDailyBriefTriggers_() {
  ScriptApp.getProjectTriggers().forEach(trigger => {
    if (trigger.getHandlerFunction() === 'sendDailyBrief') {
      ScriptApp.deleteTrigger(trigger);
    }
  });
}

function getClients_() {
  if (!CONFIG.clientSheetId) return CLIENTS;
  try {
    const sheet = SpreadsheetApp.openById(CONFIG.clientSheetId).getSheets()[0];
    const values = sheet.getDataRange().getValues();
    const header = values.shift().map(value => String(value).toLowerCase().trim());
    return values
      .filter(row => row.some(Boolean))
      .map(row => ({
        name: cell_(row, header, 'client'),
        status: cell_(row, header, 'status') || 'Active',
        raw: cell_(row, header, 'raw'),
        review: cell_(row, header, 'review'),
        final: cell_(row, header, 'final'),
        posted: cell_(row, header, 'posted'),
        editor: cell_(row, header, 'editor') || 'Confirm',
        action: cell_(row, header, 'action') || 'Check pipeline and next post.',
        priority: cell_(row, header, 'priority') || 'normal',
      }))
      .filter(client => client.name);
  } catch (error) {
    return CLIENTS.concat([{ name: 'Client source warning', status: 'Needs attention', action: `Could not read client Sheet: ${error.message}` }]);
  }
}

function getTodaysCalendar_(start, end) {
  const calendar = CalendarApp.getDefaultCalendar();
  return calendar.getEvents(start, end).map(event => ({
    title: event.getTitle(),
    start: event.getStartTime(),
    end: event.getEndTime(),
    location: event.getLocation() || '',
    description: stripHtml_(event.getDescription() || ''),
  })).filter(event => !new RegExp(CONFIG.calendarEventTitle, 'i').test(event.title));
}

// ===========================================================================
// NEWS COLLECTION
// ===========================================================================
function getNewsArticles_(memory) {
  const seen = {};
  const candidates = [];
  const cutoff = new Date(Date.now() - CONFIG.maxArticleAgeHours * 60 * 60 * 1000);

  const collect = (items) => {
    (items || []).forEach(it => {
      const title = String(it.title || '').replace(/\s+-\s+[^-]+$/, '').trim();
      const key = normalize_(title);
      if (!title || !it.link || seen[key]) return;
      if (it.published && it.published < cutoff) return;
      if (wasRecentlyUsed_(memory.articles, key)) return;
      const summary = usableSummary_(it.summary);
      const score = scoreArticle_(title, it.source || '', summary);
      if (score <= 0) return;
      seen[key] = true;
      candidates.push({
        title, link: it.link, source: it.source || 'Industry News',
        summary, published: it.published || new Date(), key, score,
      });
    });
  };

  // 1) Publisher feeds first (clean links + real summaries).
  NEWS_FEEDS.forEach(feed => {
    try { collect(fetchFeedArticles_(feed)); }
    catch (error) { Logger.log('Feed skip ' + feed.source + ': ' + error.message); }
  });

  // 2) Google News fallback only if we don't yet have enough strong picks.
  const strong = candidates.filter(c => c.score >= 8).length;
  if (strong < CONFIG.articlesToShow) {
    NEWS_QUERIES.forEach(query => {
      try { collect(fetchGoogleNewsArticles_(query)); }
      catch (error) { Logger.log('GNews skip: ' + error.message); }
    });
  }

  return candidates
    .sort((a, b) => (b.score - a.score) || (b.published.getTime() - a.published.getTime()))
    .slice(0, CONFIG.articlesToShow);
}

function fetchFeedArticles_(feed) {
  const resp = UrlFetchApp.fetch(feed.url, {
    muteHttpExceptions: true,
    followRedirects: true,
    headers: { 'User-Agent': 'Mozilla/5.0 (compatible; ShortsCreationBrief/1.0)' },
  });
  if (resp.getResponseCode() !== 200) return [];
  return parseFeed_(resp.getContentText(), feed.source);
}

function fetchGoogleNewsArticles_(query) {
  const url = 'https://news.google.com/rss/search?q=' +
    encodeURIComponent(query) + '&hl=en-US&gl=US&ceid=US:en';
  const resp = UrlFetchApp.fetch(url, { muteHttpExceptions: true, followRedirects: true });
  if (resp.getResponseCode() !== 200) return [];
  const root = XmlService.parse(resp.getContentText()).getRootElement();
  const channel = root.getChild('channel');
  const items = channel ? channel.getChildren('item') : [];
  return items.map(item => ({
    title: childText_(item, 'title'),
    link: childText_(item, 'link'),
    summary: cleanText_(childText_(item, 'description')),
    published: parseDate_(childText_(item, 'pubDate')),
    source: item.getChild('source') ? item.getChild('source').getText() : 'Google News',
  }));
}

function parseFeed_(xml, source) {
  let root;
  try { root = XmlService.parse(xml).getRootElement(); }
  catch (error) { return []; }

  const out = [];
  const channel = root.getChild('channel');

  if (channel) {
    // RSS 2.0
    const content = XmlService.getNamespace('http://purl.org/rss/1.0/modules/content/');
    channel.getChildren('item').forEach(item => {
      let summary = '';
      try { const ce = item.getChild('encoded', content); if (ce) summary = ce.getText(); } catch (e) {}
      if (!summary) summary = childText_(item, 'description');
      out.push({
        title: childText_(item, 'title'),
        link: childText_(item, 'link'),
        summary: cleanText_(summary),
        published: parseDate_(childText_(item, 'pubDate')),
        source: source,
      });
    });
  } else {
    // Atom
    const atom = XmlService.getNamespace('http://www.w3.org/2005/Atom');
    root.getChildren('entry', atom).forEach(entry => {
      let link = '';
      entry.getChildren('link', atom).forEach(l => {
        const rel = l.getAttribute('rel');
        const href = l.getAttribute('href');
        if (href && (!rel || rel.getValue() === 'alternate')) link = href.getValue();
      });
      const summary = childTextNs_(entry, 'summary', atom) || childTextNs_(entry, 'content', atom);
      out.push({
        title: childTextNs_(entry, 'title', atom),
        link: link,
        summary: cleanText_(summary),
        published: parseDate_(childTextNs_(entry, 'published', atom) || childTextNs_(entry, 'updated', atom)),
        source: source,
      });
    });
  }
  return out;
}

function buildMainThings_(events, clients, articles) {
  const highPriorityClients = clients.filter(client => /high|urgent/i.test(client.priority || '')).slice(0, 2);
  const items = [];
  if (events[0]) items.push(`Calendar anchor: ${formatTime_(events[0].start)} - ${events[0].title}.`);
  highPriorityClients.forEach(client => items.push(`Client focus: ${client.name} - ${client.action}`));
  if (articles[0]) items.push(`Content/news angle: ${articles[0].title}.`);
  items.push('Approve or create one Shorts Creation post before noon.');
  return items.slice(0, 5);
}

// ===========================================================================
// VIDEO IDEAS -- each news article becomes a real video brief:
// what it's about (context) -> Hook -> Body -> Cut/CTA -> full caption.
// ===========================================================================
function buildVideoIdeas_(articles, clients, events, memory) {
  const anchorClient = clients.find(client => /high|urgent/i.test(client.priority || '')) || clients[0] || { name: 'your top client' };
  const claudeOn = !!PropertiesService.getScriptProperties().getProperty('ANTHROPIC_API_KEY');

  const articleIdeas = articles.map(article => {
    const v = (claudeOn && enhanceWithClaude_(article)) || buildArticleVideo_(article);
    return {
      lane: 'News / useful update',
      title: article.title,
      link: article.link,
      source: article.source,
      published: article.published,
      context: v.context,
      hook: v.hook,
      body: v.body,
      cut: v.cut,
      caption: v.caption,
    };
  });

  const evergreenPool = [
    {
      lane: 'Educational',
      hook: 'Most business owners are not posting badly. They are posting without a clear reason.',
      body: 'Pick one real question a customer asked you this week. Answer it in 30 seconds, straight to camera, no fluff. That is the whole video.',
      cut: 'End with: "If your content feels random, that is the fix." Follow for one content idea a day.',
      caption: ['Your next video should answer the question your best customer is already asking. 👇', '', 'Stop guessing what to post. Open your DMs and texts, find one question a real customer asked, and answer it on camera.', '', 'Boring? No. Useful. Useful is what gets you saved, shared, and called.', '', 'Follow ' + CONFIG.instagramHandle + ' for content that brings in clients.', '', '#contentstrategy #smallbusinessmarketing #shortformvideo #miamibusiness'].join('\n'),
    },
    {
      lane: 'Contrarian',
      hook: 'Stop copying viral videos that have nothing to do with your buyer.',
      body: 'A dance trend gets views from people who will never hire you. Instead, take the FORMAT of what is working and put your expertise inside it.',
      cut: 'Close with: "Views are vanity. The right 100 people are the business." Follow for more.',
      caption: ['A trend only matters if it helps the right person trust you faster. 🎯', '', 'Vanity views feel good. They do not pay. Borrow the format, keep your message, talk to your actual buyer.', '', 'Follow ' + CONFIG.instagramHandle + ' for short-form that actually converts.', '', '#marketingtips #contentcreation #reels #businessgrowth'].join('\n'),
    },
    {
      lane: 'Client proof',
      hook: `${anchorClient.name} is proof that consistency comes from the system behind the post, not motivation.`,
      body: 'Show the pipeline: raw footage in, edit, approval, posted. The audience only sees the post. The owner needs the system that makes it happen every week.',
      cut: 'End with: "We run this for business owners so they never have to think about posting." Follow to see how.',
      caption: ['The audience only sees the post. The business owner needs the system that produces it. ⚙️', '', 'Footage -> edit -> approve -> post. Every week, without you babysitting it.', '', 'That is the difference between "I should post more" and actually growing.', '', 'Follow ' + CONFIG.instagramHandle + '.', '', '#contentsystem #smallbusiness #videomarketing #miami'].join('\n'),
    },
  ];

  const selected = [];
  articleIdeas.concat(evergreenPool).forEach(idea => {
    if (selected.length >= 5) return;
    const key = normalize_(idea.hook);
    if (wasRecentlyUsed_(memory.ideas, key)) return;
    selected.push(Object.assign({}, idea, { key }));
  });

  // Top up to 5 with evergreen if needed (memory may have eaten some).
  let i = 0;
  while (selected.length < 5 && evergreenPool.length) {
    const e = evergreenPool[i % evergreenPool.length];
    selected.push(Object.assign({}, e, { key: normalize_(e.hook + ' ' + i) }));
    i += 1;
  }

  return selected.slice(0, 5);
}

// Deterministic, article-grounded video brief (no API key needed).
function buildArticleVideo_(article) {
  const platform = detectPlatform_(article.title, article.summary);
  const summary = usableSummary_(article.summary);
  const gist = summary ? firstSentences_(summary, 2) : '';

  const context = summary
    ? truncate_(summary, 340)
    : `${platform} story: "${article.title}" (${article.source}). Open the link for the specifics, then translate it into one thing a business owner should do differently this week.`;

  const hook = `${platform} tip most business owners scroll right past 👇`;

  const body = (gist ? `Here's the gist: ${gist} ` : `Give the one key point from the article in plain English. `)
    + `For a local business owner, the takeaway is simple: turn this into ONE short video that answers what your best customer is already wondering. `
    + `Show your face, give the tip straight, and end with how to reach you.`;

  const cut = `Close with a soft CTA: "If you'd rather have this done for you, that's exactly what we do." Then: follow ${CONFIG.instagramHandle} for ${platform} tips that actually bring in clients.`;

  const caption = buildCaption_(platform, article.title, gist);
  return { context, hook, body, cut, caption };
}

function buildCaption_(platform, title, gist) {
  const tagMap = {
    'Instagram': '#instagramtips #reels #instagramgrowth #contentcreator #miamibusiness',
    'TikTok': '#tiktoktips #tiktokforbusiness #shortformvideo #contentcreator #smallbusiness',
    'YouTube': '#youtubeshorts #youtubetips #videomarketing #contentcreator #smallbusiness',
    'social media': '#socialmediatips #contentmarketing #shortformvideo #smallbusiness #miamibusiness',
  };
  const tags = tagMap[platform] || tagMap['social media'];
  const line = gist
    ? truncate_(gist, 220)
    : 'Here is the one thing worth knowing this week and why it matters for your business.';
  return [
    `${platform} tip every business owner should see 👇`,
    '',
    title,
    '',
    line,
    '',
    'What it means for you: do not chase the trend. Use it to make ONE video that answers what your best customer is already wondering about.',
    '',
    `Follow ${CONFIG.instagramHandle} for short-form that actually brings in clients.`,
    '',
    tags,
  ].join('\n');
}

// OPTIONAL: sharpen the brief with Claude when ANTHROPIC_API_KEY is set.
function enhanceWithClaude_(article) {
  const prompt = [
    'You write short-form video briefs for a Miami short-form content agency (Shorts Creation).',
    'The people watching these videos are LOCAL BUSINESS OWNERS the agency wants as clients.',
    'You are given ONE industry news article. Return STRICT JSON only (no markdown fences), with keys:',
    'context, hook, body, cut, caption.',
    "- context: 2 plain-English sentences on what the article is about and why a business owner should care. Use only facts from the title/summary; if the summary is thin, say what it likely covers and to open the link. Never invent stats.",
    '- hook: one scroll-stopping first line for the video.',
    '- body: 2-4 sentences of what to say on camera (what changed -> why it matters to a business owner -> the ONE move to make).',
    '- cut: the closing line / call to action on camera.',
    '- caption: a full ready-to-post caption (3-6 short lines) ending with 3-5 relevant hashtags, and include ' + CONFIG.instagramHandle + ' as the follow CTA.',
    'Punchy and useful, not hypey. Never suggest buying followers/views/engagement.',
    '',
    'ARTICLE TITLE: ' + article.title,
    'SOURCE: ' + (article.source || ''),
    'SUMMARY: ' + (usableSummary_(article.summary) || '(no summary available)'),
  ].join('\n');

  const text = callClaude_(prompt);
  if (!text) return null;
  try {
    const json = JSON.parse(String(text).replace(/^```json\s*|\s*```$/g, '').trim());
    if (json && json.hook && json.caption) {
      return {
        context: json.context || '',
        hook: json.hook,
        body: json.body || '',
        cut: json.cut || '',
        caption: json.caption,
      };
    }
  } catch (error) {
    Logger.log('Claude JSON parse failed: ' + error.message);
  }
  return null;
}

function callClaude_(prompt) {
  const key = PropertiesService.getScriptProperties().getProperty('ANTHROPIC_API_KEY');
  if (!key) return null;
  try {
    const resp = UrlFetchApp.fetch('https://api.anthropic.com/v1/messages', {
      method: 'post',
      contentType: 'application/json',
      muteHttpExceptions: true,
      headers: { 'x-api-key': key, 'anthropic-version': '2023-06-01' },
      payload: JSON.stringify({
        model: CONFIG.claudeModel,
        max_tokens: 800,
        messages: [{ role: 'user', content: prompt }],
      }),
    });
    if (resp.getResponseCode() !== 200) {
      Logger.log('Claude HTTP ' + resp.getResponseCode() + ': ' + resp.getContentText().slice(0, 300));
      return null;
    }
    const data = JSON.parse(resp.getContentText());
    return (data.content && data.content[0] && data.content[0].text) || null;
  } catch (error) {
    Logger.log('Claude error: ' + error.message);
    return null;
  }
}

function buildPlainTextBrief_(dateLabel, mainThings, events, clients, articles, ideas, memory) {
  const lines = [];
  lines.push(`${CONFIG.businessName} Daily Brief - ${dateLabel}`);
  lines.push('');
  lines.push('Main Things Today');
  mainThings.forEach((item, index) => lines.push(`${index + 1}. ${item}`));
  lines.push('');
  lines.push("Today's Calendar");
  if (!events.length) lines.push('No calendar events today.');
  events.forEach(event => {
    lines.push(`- ${formatTime_(event.start)} ${event.title}${event.location ? ` (${event.location})` : ''}`);
    if (event.description) lines.push(`  Notes: ${truncate_(event.description, 220)}`);
  });
  lines.push('');
  lines.push('Client Snapshot');
  clients.forEach(client => {
    const counts = [client.raw, client.review, client.final, client.posted].filter(value => value !== '' && value !== undefined).length
      ? ` Raw ${client.raw || 0} / Review ${client.review || 0} / Final ${client.final || 0} / Posted ${client.posted || 0}.`
      : '';
    lines.push(`- ${client.name}: ${client.status || 'Active'}.${counts} Editor: ${client.editor || 'Confirm'}. Action: ${client.action || 'Check pipeline.'}`);
  });
  lines.push('');
  lines.push(`Industry Articles Today (${articles.length})`);
  articles.forEach((article, index) => {
    lines.push(`${index + 1}. ${article.title} - ${article.source}`);
    if (article.link) lines.push(`   ${article.link}`);
    if (usableSummary_(article.summary)) lines.push(`   ${truncate_(usableSummary_(article.summary), 240)}`);
  });
  lines.push('');
  lines.push(`Video Ideas (${ideas.length})`);
  ideas.forEach((idea, index) => {
    lines.push('');
    if (idea.link) {
      lines.push(`${index + 1}. [${idea.lane}] ${idea.title} - ${idea.source}`);
      lines.push(`   Link: ${idea.link}`);
      if (idea.context) lines.push(`   What it's about: ${idea.context}`);
    } else {
      lines.push(`${index + 1}. [${idea.lane}]`);
    }
    lines.push(`   Hook: ${idea.hook}`);
    if (idea.body) lines.push(`   Body: ${idea.body}`);
    if (idea.cut) lines.push(`   Cut / CTA: ${idea.cut}`);
    lines.push(`   Caption:`);
    String(idea.caption || '').split('\n').forEach(cl => lines.push(`   ${cl}`));
  });
  lines.push('');
  lines.push(`Memory: avoiding articles and hooks used in the last ${CONFIG.memoryLookbackDays} days. Recent idea memory: ${memory.ideas.length} items.`);
  return lines.join('\n');
}

function buildHtmlBrief_(dateLabel, mainThings, events, clients, articles, ideas, memory) {
  const clientRows = clients.map(client => {
    const counts = [client.raw, client.review, client.final, client.posted].filter(value => value !== '' && value !== undefined).length
      ? `R:${client.raw || 0} / Rv:${client.review || 0} / F:${client.final || 0} / P:${client.posted || 0}`
      : 'Connect live counts';
    return `<tr>
      <td>${escapeHtml_(client.name)}</td>
      <td>${escapeHtml_(client.status || 'Active')}</td>
      <td>${escapeHtml_(counts)}</td>
      <td>${escapeHtml_(client.editor || 'Confirm')}</td>
      <td>${escapeHtml_(client.action || 'Check pipeline.')}</td>
    </tr>`;
  }).join('');

  return `
    <div style="font-family:Arial,sans-serif;line-height:1.45;color:#111;max-width:860px">
      <h1 style="margin:0 0 4px">${escapeHtml_(CONFIG.businessName)} Daily Brief</h1>
      <div style="color:#666;margin-bottom:20px">${escapeHtml_(dateLabel)} · Miami time</div>

      <h2>Main Things Today</h2>
      <ol>${mainThings.map(item => `<li>${escapeHtml_(item)}</li>`).join('')}</ol>

      <h2>Today's Calendar</h2>
      ${events.length ? `<ul>${events.map(event => `
        <li>
          <strong>${escapeHtml_(formatTime_(event.start))}</strong>
          ${escapeHtml_(event.title)}
          ${event.location ? ` · ${escapeHtml_(event.location)}` : ''}
          ${event.description ? `<br><span style="color:#555">${escapeHtml_(truncate_(event.description, 220))}</span>` : ''}
        </li>`).join('')}</ul>` : '<p>No calendar events today.</p>'}

      <h2>Client Snapshot</h2>
      <table cellpadding="8" cellspacing="0" style="border-collapse:collapse;width:100%;font-size:14px">
        <thead>
          <tr style="background:#f2f4f7;text-align:left">
            <th>Client</th><th>Status</th><th>Pipeline</th><th>Editor</th><th>Action today</th>
          </tr>
        </thead>
        <tbody>${clientRows}</tbody>
      </table>
      <p style="color:#777;font-size:12px">Live raw/review/final/posted counts appear once the client Sheet or Dropbox source is connected.</p>

      <h2>Industry Articles Today (${articles.length})</h2>
      <ol>${articles.map(article => `
        <li style="margin-bottom:10px">
          <strong>${article.link ? `<a href="${escapeAttr_(article.link)}">${escapeHtml_(article.title)}</a>` : escapeHtml_(article.title)}</strong>
          <br><span style="color:#555">${escapeHtml_(article.source || 'Source')} · ${escapeHtml_(formatDate_(article.published))}</span>
          ${usableSummary_(article.summary) ? `<br><span style="color:#333">${escapeHtml_(truncate_(usableSummary_(article.summary), 240))}</span>` : ''}
        </li>`).join('')}</ol>

      <h2>Video Ideas (${ideas.length})</h2>
      <ol>${ideas.map(idea => `
        <li style="margin-bottom:20px">
          ${idea.link
            ? `<strong>${idea.link ? `<a href="${escapeAttr_(idea.link)}">${escapeHtml_(idea.title)}</a>` : escapeHtml_(idea.title)}</strong>
               <div style="color:#777;font-size:12px">${escapeHtml_(idea.lane)} · ${escapeHtml_(idea.source || '')}${idea.published ? ` · ${escapeHtml_(formatDate_(idea.published))}` : ''}</div>
               ${idea.context ? `<div style="margin:6px 0"><strong>What it's about:</strong> ${escapeHtml_(idea.context)}</div>` : ''}`
            : `<strong>${escapeHtml_(idea.lane)}</strong>`}
          <div style="margin:6px 0"><strong>Hook:</strong> ${escapeHtml_(idea.hook)}</div>
          ${idea.body ? `<div style="margin:6px 0"><strong>Body:</strong> ${escapeHtml_(idea.body)}</div>` : ''}
          ${idea.cut ? `<div style="margin:6px 0"><strong>Cut / CTA:</strong> ${escapeHtml_(idea.cut)}</div>` : ''}
          <div style="margin:6px 0;background:#f7f8fa;border-left:3px solid #c7ccd6;padding:8px 12px">
            <strong>Caption:</strong><br>${escapeHtml_(idea.caption || '').replace(/\n/g, '<br>')}
          </div>
        </li>`).join('')}</ol>

      <p style="color:#777;font-size:12px">Memory: avoiding articles and hooks used in the last ${CONFIG.memoryLookbackDays} days. Recent idea memory: ${escapeHtml_(memory.ideas.length)} items.</p>
    </div>`;
}

function upsertCalendarBlock_(day, briefText) {
  const calendar = CalendarApp.getDefaultCalendar();
  const start = new Date(day);
  start.setHours(CONFIG.sendHour, 0, 0, 0);
  const end = new Date(start.getTime() + CONFIG.calendarBlockMinutes * 60 * 1000);

  calendar.getEvents(start, end, { search: CONFIG.calendarEventTitle })
    .filter(event => event.getTitle() === CONFIG.calendarEventTitle)
    .forEach(event => event.deleteEvent());

  calendar.createEvent(CONFIG.calendarEventTitle, start, end, {
    description: briefText,
  });
}

// ===========================================================================
// SCORING -- spam-proof and tuned for "actionable / get-seen / make-better-
// videos" news. Returns 0 to reject an article outright.
// ===========================================================================
function scoreArticle_(title, source, summary) {
  const text = normalize_(`${title} ${summary || ''} ${source}`);
  const titleNorm = normalize_(title);

  // Hard kill switches: spam first, then off-topic/doom.
  if (SPAM_BLOCKLIST.some(term => text.indexOf(normalize_(term)) !== -1)) return 0;
  if (OFFTOPIC_BLOCKLIST.some(term => text.indexOf(normalize_(term)) !== -1)) return 0;
  // Kill bare category/hub titles like "Social Media Platforms".
  if (titleNorm.split(' ').filter(Boolean).length < 4) return 0;

  const platformHit = PLATFORM_TERMS.some(term => text.indexOf(normalize_(term)) !== -1);
  const industryHit = INDUSTRY_TERMS.some(term => text.indexOf(normalize_(term)) !== -1);
  if (!platformHit && !industryHit) return 0;

  let score = 0;
  if (platformHit) score += 6;
  // Platform named in the HEADLINE = real platform news -> float it to the top
  // above generic "social media marketing" guides.
  if (platformOf_(titleNorm)) score += 8;
  INDUSTRY_TERMS.forEach(term => { if (text.indexOf(normalize_(term)) !== -1) score += 1; });
  ACTIONABLE_TERMS.forEach(term => { if (text.indexOf(normalize_(term)) !== -1) score += 2; });
  GROWTH_TERMS.forEach(term => { if (text.indexOf(normalize_(term)) !== -1) score += 2; });
  if (TRUSTED_NEWS_SOURCES.some(src => normalize_(source).indexOf(normalize_(src)) !== -1)) score += 4;
  if (usableSummary_(summary).length > 120) score += 2; // real context to build a video from
  if (LOCAL_TARGET_TERMS.some(term => text.indexOf(normalize_(term)) !== -1)) score += 1;
  return score;
}

// Detect platform from the HEADLINE first. Long marketing articles mention
// every platform in the body, so scanning the summary would mislabel them --
// we only fall back to the summary when the title names exactly one platform.
function detectPlatform_(title, summary) {
  const fromTitle = platformOf_(normalize_(title || ''));
  if (fromTitle) return fromTitle;
  const t = normalize_(summary || '');
  const hits = {
    TikTok: /tiktok/.test(t),
    YouTube: /youtube|shorts/.test(t),
    Instagram: /instagram|reels|threads/.test(t),
  };
  const named = Object.keys(hits).filter(k => hits[k]);
  if (named.length === 1) return named[0]; // only one platform in play -> safe
  return 'social media';
}

function platformOf_(t) {
  if (/tiktok/.test(t)) return 'TikTok';
  if (/youtube|shorts/.test(t)) return 'YouTube';
  if (/instagram|reels|reel|threads/.test(t)) return 'Instagram';
  return '';
}

// Split into the first N sentences, capped, so the brief reads like talking
// points instead of a dumped paragraph.
function firstSentences_(text, n) {
  const clean = String(text || '').trim();
  if (!clean) return '';
  const parts = clean.split(/(?<=[.!?])\s+/);
  let out = parts.slice(0, n).join(' ').trim();
  if (out.length > 260) out = truncate_(out, 260);
  return out;
}

function shortTopic_(title) {
  return truncate_(String(title || '').replace(/[:.]+$/, '').trim(), 90);
}

function usableSummary_(s) {
  if (!s) return '';
  const t = String(s).trim();
  if (t.length < 40) return '';
  if (/view full coverage|read more on|google news|continue reading|\[…\]/i.test(t)) {
    const cleaned = t.replace(/view full coverage.*$/i, '').trim();
    return cleaned.length >= 40 ? cleaned : '';
  }
  return t;
}

function loadMemory_() {
  const empty = { articles: [], ideas: [], runs: [], picked: [] };
  try {
    const value = PropertiesService.getScriptProperties().getProperty(CONFIG.memoryKey);
    if (!value) return empty;
    const parsed = JSON.parse(value);
    return pruneMemory_(Object.assign(empty, parsed));
  } catch (error) {
    return empty;
  }
}

function rememberRun_(memory, dateLabel, articles, ideas) {
  const now = new Date();
  const run = {
    date: Utilities.formatDate(now, CONFIG.timezone, 'yyyy-MM-dd'),
    label: dateLabel,
    articleTitles: articles.map(article => article.title),
    ideaHooks: ideas.map(idea => idea.hook),
  };

  articles.forEach(article => {
    memory.articles.push({
      key: article.key || normalize_(article.title),
      title: article.title,
      source: article.source,
      link: article.link,
      usedAt: now.toISOString(),
    });
  });

  ideas.forEach(idea => {
    memory.ideas.push({
      key: idea.key || normalize_(idea.hook),
      hook: idea.hook,
      lane: idea.lane,
      usedAt: now.toISOString(),
    });
  });

  memory.runs.push(run);
  saveMemory_(pruneMemory_(memory));
}

function saveMemory_(memory) {
  const json = JSON.stringify(memory, null, 2);
  PropertiesService.getScriptProperties().setProperty(CONFIG.memoryKey, json);
}

function pruneMemory_(memory) {
  const cutoff = Date.now() - CONFIG.memoryLookbackDays * 24 * 60 * 60 * 1000;
  memory.articles = dedupeMemory_((memory.articles || []).filter(item => Date.parse(item.usedAt || 0) >= cutoff));
  memory.ideas = dedupeMemory_((memory.ideas || []).filter(item => Date.parse(item.usedAt || 0) >= cutoff));
  memory.runs = (memory.runs || []).slice(-45);
  memory.picked = (memory.picked || []).slice(-100);
  return memory;
}

function dedupeMemory_(items) {
  const seen = {};
  return items.filter(item => {
    const key = item.key || normalize_(item.title || item.hook || '');
    if (!key || seen[key]) return false;
    seen[key] = true;
    item.key = key;
    return true;
  });
}

function wasRecentlyUsed_(items, key) {
  return (items || []).some(item => item.key === key);
}

function cell_(row, header, name) {
  const index = header.indexOf(name);
  return index === -1 ? '' : row[index];
}

function text_(item, childName) {
  const child = item.getChild(childName);
  return child ? child.getText() : '';
}

function childText_(item, childName) {
  const child = item.getChild(childName);
  return child ? child.getText() : '';
}

function childTextNs_(item, childName, ns) {
  const child = item.getChild(childName, ns);
  return child ? child.getText() : '';
}

function parseDate_(value) {
  const date = new Date(value);
  return isNaN(date.getTime()) ? new Date() : date;
}

function formatDate_(date) {
  return Utilities.formatDate(date || new Date(), CONFIG.timezone, 'MMM d, h:mm a');
}

function normalize_(value) {
  return String(value).toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();
}

function startOfDay_(date) {
  const copy = new Date(date);
  copy.setHours(0, 0, 0, 0);
  return copy;
}

function addDays_(date, days) {
  const copy = new Date(date);
  copy.setDate(copy.getDate() + days);
  return copy;
}

function formatTime_(date) {
  return Utilities.formatDate(date, CONFIG.timezone, 'h:mm a');
}

function stripHtml_(value) {
  return value.replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim();
}

function cleanText_(html) {
  if (!html) return '';
  return String(html)
    .replace(/<script[\s\S]*?<\/script>/gi, ' ')
    .replace(/<style[\s\S]*?<\/style>/gi, ' ')
    .replace(/<[^>]+>/g, ' ')
    .replace(/&nbsp;/gi, ' ')
    .replace(/&amp;/gi, '&')
    .replace(/&#0*39;|&rsquo;|&lsquo;|&#82(16|17);/g, "'")
    .replace(/&quot;|&#822[01];|&ldquo;|&rdquo;/gi, '"')
    .replace(/&#8230;|&hellip;/gi, '...')
    .replace(/&#82(11|12);|&[mn]dash;/gi, '-')
    // Decode any remaining numeric entities (decimal + hex), e.g. &#8217; &#x2019;
    .replace(/&#x([0-9a-f]+);/gi, (m, h) => safeFromCharCode_(parseInt(h, 16)))
    .replace(/&#(\d+);/g, (m, d) => safeFromCharCode_(parseInt(d, 10)))
    .replace(/&[a-z]+;/gi, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function safeFromCharCode_(code) {
  try { return isNaN(code) ? ' ' : String.fromCharCode(code); }
  catch (e) { return ' '; }
}

function truncate_(value, maxLength) {
  const v = String(value || '');
  return v.length > maxLength ? `${v.slice(0, maxLength - 3)}...` : v;
}

function escapeHtml_(value) {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function escapeAttr_(value) {
  return escapeHtml_(value).replace(/`/g, '&#96;');
}
