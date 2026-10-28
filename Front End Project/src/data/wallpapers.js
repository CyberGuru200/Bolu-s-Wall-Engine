const wallpapers = [
  //Anime(6) 
  {
    id: 1,
    title: "Seoul Street Art",
    url: "https://images.pexels.com/photos/32014936/pexels-photo-32014936.jpeg?auto=compress&cs=tinysrgb&fit=crop&h=627&w=1200",
    category: "Anime",
  },
  {
    id: 2,
    title: "Akihabara Neon Night",
    url: "https://images.pexels.com/photos/33249534/pexels-photo-33249534.jpeg?auto=compress&cs=tinysrgb&fit=crop&h=627&w=1200",
    category: "Anime",
  },
  {
    id: 3,
    title: "Tokyo Night Streets",
    url: "https://images.pexels.com/photos/30780336/pexels-photo-30780336.jpeg?auto=compress&cs=tinysrgb&fit=crop&h=627&w=1200",
    category: "Anime",
  },
  {
    id: 4,
    title: "Japanese Alleyway",
    url: "https://images.pexels.com/photos/29518215/pexels-photo-29518215.jpeg?auto=compress&cs=tinysrgb&fit=crop&h=627&w=1200",
    category: "Anime",
  },
  {
    id: 5,
    title: "Shinjuku Neon Glow",
    url: "https://images.pexels.com/photos/31023684/pexels-photo-31023684.jpeg?auto=compress&cs=tinysrgb&fit=crop&h=627&w=1200",
    category: "Anime",
  },
  {
    id: 6,
    title: "Tokyo Neon Signs",
    url: "https://images.pexels.com/photos/2067048/pexels-photo-2067048.jpeg?auto=compress&cs=tinysrgb&fit=crop&h=627&w=1200",
    category: "Anime",
  },

  //Abstract(6)
  {
    id: 7,
    title: "Dark Fluid Gradient",
    url: "https://images.pexels.com/photos/6985268/pexels-photo-6985268.jpeg?auto=compress&cs=tinysrgb&fit=crop&h=627&w=1200",
    category: "Abstract",
  },
  {
    id: 8,
    title: "Expressionist Splash",
    url: "https://images.pexels.com/photos/31009982/pexels-photo-31009982.jpeg?auto=compress&cs=tinysrgb&fit=crop&h=627&w=1200",
    category: "Abstract",
  },
  {
    id: 9,
    title: "Marble Swirl Texture",
    url: "https://images.pexels.com/photos/15272522/pexels-photo-15272522.jpeg?auto=compress&cs=tinysrgb&fit=crop&h=627&w=1200",
    category: "Abstract",
  },
  {
    id: 10,
    title: "Digital Expressionism",
    url: "https://images.pexels.com/photos/31023736/pexels-photo-31023736.jpeg?auto=compress&cs=tinysrgb&fit=crop&h=627&w=1200",
    category: "Abstract",
  },
  {
    id: 11,
    title: "Acrylic Paint Vortex",
    url: "https://images.pexels.com/photos/11105655/pexels-photo-11105655.jpeg?auto=compress&cs=tinysrgb&fit=crop&h=627&w=1200",
    category: "Abstract",
  },
  {
    id: 12,
    title: "Fluid Color Streams",
    url: "https://images.pexels.com/photos/14921309/pexels-photo-14921309.jpeg?auto=compress&cs=tinysrgb&fit=crop&h=627&w=1200",
    category: "Abstract",
  },

  // Minimalist(6)
  {
    id: 13,
    title: "Geometric Shapes Dark",
    url: "https://images.pexels.com/photos/28586307/pexels-photo-28586307.jpeg?auto=compress&cs=tinysrgb&fit=crop&h=627&w=1200",
    category: "Minimalist",
  },
  {
    id: 14,
    title: "Modern Facade",
    url: "https://images.pexels.com/photos/3137084/pexels-photo-3137084.jpeg?auto=compress&cs=tinysrgb&fit=crop&h=627&w=1200",
    category: "Minimalist",
  },
  {
    id: 15,
    title: "Dark Spiral Art",
    url: "https://images.pexels.com/photos/30004061/pexels-photo-30004061.jpeg?auto=compress&cs=tinysrgb&fit=crop&h=627&w=1200",
    category: "Minimalist",
  },
  {
    id: 16,
    title: "Elegant Gray Waves",
    url: "https://images.pexels.com/photos/29708304/pexels-photo-29708304.jpeg?auto=compress&cs=tinysrgb&fit=crop&h=627&w=1200",
    category: "Minimalist",
  },
  {
    id: 17,
    title: "Abstract Lines",
    url: "https://images.pexels.com/photos/29339881/pexels-photo-29339881.jpeg?auto=compress&cs=tinysrgb&fit=crop&h=627&w=1200",
    category: "Minimalist",
  },
  {
    id: 18,
    title: "Ceiling Geometry",
    url: "https://images.pexels.com/photos/17709758/pexels-photo-17709758.jpeg?auto=compress&cs=tinysrgb&fit=crop&h=627&w=1200",
    category: "Minimalist",
  },

  //Colored(6)
  {
    id: 19,
    title: "Rainbow LED Tubes",
    url: "https://images.pexels.com/photos/10196790/pexels-photo-10196790.jpeg?auto=compress&cs=tinysrgb&fit=crop&h=627&w=1200",
    category: "Colored",
  },
  {
    id: 20,
    title: "Iridescent Fabric",
    url: "https://images.pexels.com/photos/38394972/pexels-photo-38394972.jpeg?auto=compress&cs=tinysrgb&fit=crop&h=627&w=1200",
    category: "Colored",
  },
  {
    id: 21,
    title: "Violet Pink Lights",
    url: "https://images.pexels.com/photos/7130540/pexels-photo-7130540.jpeg?auto=compress&cs=tinysrgb&fit=crop&h=627&w=1200",
    category: "Colored",
  },
  {
    id: 22,
    title: "Neon Gradient Art",
    url: "https://images.pexels.com/photos/29355994/pexels-photo-29355994.jpeg?auto=compress&cs=tinysrgb&fit=crop&h=627&w=1200",
    category: "Colored",
  },
  {
    id: 23,
    title: "Pink Purple Gradient",
    url: "https://images.pexels.com/photos/6985272/pexels-photo-6985272.jpeg?auto=compress&cs=tinysrgb&fit=crop&h=627&w=1200",
    category: "Colored",
  },
  {
    id: 24,
    title: "Neon Prism Effect",
    url: "https://images.pexels.com/photos/29751268/pexels-photo-29751268.jpeg?auto=compress&cs=tinysrgb&fit=crop&h=627&w=1200",
    category: "Colored",
  },
];

export default wallpapers;
