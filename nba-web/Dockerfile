FROM nginx:alpine

# La conf par défaut est remplacé pour servir index.html correctement
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Static files
COPY . /usr/share/nginx/html

EXPOSE 80
