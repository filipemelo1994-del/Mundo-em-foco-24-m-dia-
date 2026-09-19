export default async (request) => {
  if (request.method !== "POST") return new Response("Method not allowed", { status: 405 });

  const key = request.headers.get("x-upload-key");
  if (!process.env.MEDIA_UPLOAD_KEY || key !== process.env.MEDIA_UPLOAD_KEY) {
    return new Response("Unauthorized", { status: 401 });
  }

  const token = process.env.GITHUB_MEDIA_TOKEN;
  if (!token) return new Response("GITHUB_MEDIA_TOKEN not configured", { status: 500 });

  const form = await request.formData();
  const file = form.get("file");
  const requestedName = String(form.get("name") || file?.name || "imagem.jpg");
  if (!file || typeof file.arrayBuffer !== "function") return new Response("File missing", { status: 400 });

  const type = file.type || "";
  if (!["image/jpeg","image/png","image/webp"].includes(type)) return new Response("Unsupported image type", { status: 415 });
  if (file.size > 8 * 1024 * 1024) return new Response("File too large", { status: 413 });

  const safe = requestedName.toLowerCase().replace(/[^a-z0-9._-]+/g, "-").replace(/^-+|-+$/g, "");
  const bytes = new Uint8Array(await file.arrayBuffer());
  let binary = "";
  for (let i=0; i<bytes.length; i+=0x8000) binary += String.fromCharCode(...bytes.subarray(i,i+0x8000));
  const content = btoa(binary);

  const owner = "filipemelo1994-del";
  const repo = "Mundo-em-foco-24-m-dia-";
  const path = "midia/" + safe;
  const api = "https://api.github.com/repos/" + owner + "/" + repo + "/contents/" + path;

  const gh = await fetch(api, {
    method: "PUT",
    headers: {
      "Authorization": "Bearer " + token,
      "Accept": "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ message: "Upload de mídia: " + safe, content, branch: "main" })
  });

  const result = await gh.json();
  if (!gh.ok) return Response.json({ ok:false, github:result }, { status:gh.status });

  return Response.json({
    ok:true,
    path,
    raw_url:"https://raw.githubusercontent.com/"+owner+"/"+repo+"/main/"+path,
    portal_url:"https://mundoemfoco24.netlify.app/"+path,
    commit: result.commit?.sha || null
  });
};
