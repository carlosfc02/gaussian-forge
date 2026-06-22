from pathlib import Path


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text()
    if old not in text:
        raise RuntimeError(f"Could not find expected text in {path}: {old[:120]!r}")
    path.write_text(text.replace(old, new, 1))


train_path = Path("train.py")

replace_once(
    train_path,
    "                l1_test = 0.0\n"
    "                psnr_test = 0.0\n",
    "                l1_test = 0.0\n"
    "                psnr_test = 0.0\n"
    "                ssim_test = 0.0\n",
)

replace_once(
    train_path,
    "                    l1_test += l1_loss(image, gt_image).mean().double()\n"
    "                    psnr_test += psnr(image, gt_image).mean().double()\n",
    "                    l1_test += l1_loss(image, gt_image).mean().double()\n"
    "                    psnr_test += psnr(image, gt_image).mean().double()\n"
    "                    if FUSED_SSIM_AVAILABLE:\n"
    "                        ssim_test += fused_ssim(image.unsqueeze(0), gt_image.unsqueeze(0)).mean().double()\n"
    "                    else:\n"
    "                        ssim_test += ssim(image, gt_image).mean().double()\n",
)

replace_once(
    train_path,
    "                psnr_test /= len(config['cameras'])\n"
    "                l1_test /= len(config['cameras'])          \n"
    "                print(\"\\n[ITER {}] Evaluating {}: L1 {} PSNR {}\".format(iteration, config['name'], l1_test, psnr_test))\n",
    "                psnr_test /= len(config['cameras'])\n"
    "                l1_test /= len(config['cameras'])\n"
    "                ssim_test /= len(config['cameras'])\n"
    "                print(\"\\n[ITER {}] Evaluating {}: L1 {} PSNR {} SSIM {}\".format(iteration, config['name'], l1_test, psnr_test, ssim_test))\n",
)

replace_once(
    train_path,
    "                    tb_writer.add_scalar(config['name'] + '/loss_viewpoint - psnr', psnr_test, iteration)\n",
    "                    tb_writer.add_scalar(config['name'] + '/loss_viewpoint - psnr', psnr_test, iteration)\n"
    "                    tb_writer.add_scalar(config['name'] + '/loss_viewpoint - ssim', ssim_test, iteration)\n",
)
