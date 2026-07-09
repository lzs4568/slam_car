#pragma once
#include <vector>
#include <cstring>
#include <rockchip/rk_mpi.h>
#include <rockchip/rk_type.h>

namespace slam_car_yolo {

/// RK3588 MPP 硬件 JPEG 编码器 (NV12 → JPEG)
class MppJpegEncoder {
public:
    bool init(int width, int height, int quality = 60);
    bool encode(const uint8_t* nv12_data, std::vector<uint8_t>& jpeg_out);
    ~MppJpegEncoder();

private:
    MppCtx   ctx_  = nullptr;
    MppApi*  mpi_  = nullptr;
    MppEncCfg cfg_ = nullptr;
    int width_  = 0;
    int height_ = 0;
};

/// 简单 BGR24 → NV12 转换 (单线程, 终端节点 — YOLO内部已完成推理)
inline void bgr_to_nv12(const uint8_t* bgr, int width, int height,
                         uint8_t* y_plane, uint8_t* uv_plane) {
    for (int row = 0; row < height; row++) {
        for (int col = 0; col < width; col++) {
            int idx = (row * width + col) * 3;
            int B = bgr[idx];
            int G = bgr[idx + 1];
            int R = bgr[idx + 2];

            // Y  =  0.299R + 0.587G + 0.114B  (ITU-R BT.601)
            int Y_val = (( 66 * R + 129 * G +  25 * B + 128) >> 8) + 16;
            y_plane[row * width + col] = (uint8_t)(Y_val < 0 ? 0 : (Y_val > 255 ? 255 : Y_val));

            if ((row & 1) == 0 && (col & 1) == 0) {
                int uv_idx = (row / 2) * (width / 2) + (col / 2);
                // U = -0.169R - 0.331G + 0.500B + 128
                int U_val = ((-38 * R - 74 * G + 112 * B + 128) >> 8) + 128;
                // V =  0.500R - 0.419G - 0.081B + 128
                int V_val = ((112 * R - 94 * G - 18 * B + 128) >> 8) + 128;
                uv_plane[uv_idx * 2]     = (uint8_t)(U_val < 0 ? 0 : (U_val > 255 ? 255 : U_val));
                uv_plane[uv_idx * 2 + 1] = (uint8_t)(V_val < 0 ? 0 : (V_val > 255 ? 255 : V_val));
            }
        }
    }
}

}  // namespace slam_car_yolo
