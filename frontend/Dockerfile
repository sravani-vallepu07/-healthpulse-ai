FROM nginx:alpine

# Copy static frontend files to nginx html root
COPY . /usr/share/nginx/html

# Expose port
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
