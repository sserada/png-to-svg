# PNG to SVG

This tool allows users to convert PNG images to SVG format. Users can upload PNG files through a user-friendly frontend interface and get the converted SVGs as downloadable ZIP files. The frontend is developed using Svelte, a modern component framework, while the backend leverages FastAPI, a fast and efficient web framework for building APIs.

https://github.com/fightingsou/png-to-svg/assets/104222305/a33c68de-1575-42ab-b524-ecc5016f263c

### Features
- Upload: Users can upload PNG files via drag and drop or file selection.
- PNG to SVG Conversion: Once the PNG files are uploaded, they are sent to the backend for conversion to SVG format.
- Download: Users can download all the converted SVG files as a ZIP archive.

### Startup Procedure

1. Clone the repository by running the following command

```
git clone https://dsrg.backlog.com/git/WEBAPI/beach-litter-segmentation.git
cd beach-litter-segmentation
```

2. Change `sapmle.env` to `.env` with the following command
```
mv sample.env .env
```

3. Change the contents of `.env`

- For IP, enter the IP address where you want to set up the server; you can use the `ip a` command to find out the IP address configured on your PC (usually found in the inet of `eth~` or `enp~`)

- For `FRONTEND_PORT` and `BACKEND_PORT`, enter the port numbers on which you want to start the front-end and back-end servers.

```
IP=0.0.0.0
FRONTEND_PORT=55030
BACKEND_PORT=55031
```
4. Run the following command to start

```
sudo docker-compose up -d
```

5. Go to the following URL
> http://{IP}:{FRONTEND_PORT}


